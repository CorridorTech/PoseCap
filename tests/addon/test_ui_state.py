import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import posecap_addon.panels
from posecap_addon.engine_process import EngineEndpoint, EngineProcess
from posecap_addon.panels import (
    ADDON_ID,
    SCENE_PROPERTY_NAME,
    draw_addon_preferences,
    draw_live_stream_panel,
    register_blender_ui,
    unregister_blender_ui,
)
from posecap_addon.stream_client import TcpPoseStreamClient
from posecap_addon.ui_state import LifecycleState, lifecycle_controls
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    PoseFrame,
    PosePayload,
)


def test_lifecycle_controls_match_stream_state_machine() -> None:
    assert lifecycle_controls("STOPPED").can_start
    assert not lifecycle_controls("STOPPED").can_stop

    assert not lifecycle_controls("STARTING").can_start
    assert lifecycle_controls("STARTING").can_stop

    assert not lifecycle_controls("STREAMING").can_start
    assert lifecycle_controls("STREAMING").can_stop
    assert lifecycle_controls("STREAMING").can_record

    assert lifecycle_controls("RECORDING").is_recording
    assert lifecycle_controls("RECORDING").can_record

    assert lifecycle_controls("RECONNECTING").can_stop
    assert not lifecycle_controls("RECONNECTING").can_record

    warning = lifecycle_controls("WARNING", status_message="target armature is unavailable")
    assert warning.can_stop
    assert warning.status_text == "target armature is unavailable"


def test_live_stream_panel_draws_state_controls_from_lifecycle() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(lifecycle_state="STOPPED"))

    assert layout.enabled_for_operator("posecap.start_stream")
    assert not layout.enabled_for_operator("posecap.stop_stream")
    assert not layout.enabled_for_property("record_live_mocap")
    assert layout.has_property("target_armature")
    assert layout.has_label("Stopped")


def test_addon_preferences_draw_runtime_defaults() -> None:
    layout = _FakeLayout()
    preferences = _FakeAddonPreferences(
        pear_root="C:/PEAR",
        engine_executable="C:/PoseCap/posecap-engine.exe",
    )

    draw_addon_preferences(layout, preferences)

    assert layout.has_property("pear_root")
    assert layout.has_property("engine_executable")


def test_blender_ui_registration_adds_scene_state_and_unregisters_cleanly() -> None:
    bpy = _FakeBpy()

    register_blender_ui(bpy)

    assert [cls.__name__ for cls in bpy.utils.registered] == [
        "POSECAP_PG_LiveStreamSettings",
        "POSECAP_AP_AddonPreferences",
        "POSECAP_OT_StartStream",
        "POSECAP_OT_StopStream",
        "POSECAP_PT_LiveStream",
    ]
    preferences_cls = bpy.utils.registered_class("POSECAP_AP_AddonPreferences")
    assert preferences_cls.bl_idname == ADDON_ID
    assert getattr(bpy.types.Scene, SCENE_PROPERTY_NAME)[0] == "PointerProperty"

    unregister_blender_ui(bpy)
    unregister_blender_ui(bpy)

    assert not hasattr(bpy.types.Scene, SCENE_PROPERTY_NAME)
    assert [cls.__name__ for cls in bpy.utils.unregistered] == [
        "POSECAP_PT_LiveStream",
        "POSECAP_OT_StopStream",
        "POSECAP_OT_StartStream",
        "POSECAP_AP_AddonPreferences",
        "POSECAP_PG_LiveStreamSettings",
    ]


def test_start_and_stop_operators_own_stream_runtime(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.camera_index = 4
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []
    commands: list[tuple[str, ...]] = []

    def fake_start_engine_stream(command):
        commands.append(tuple(command))
        return engine

    def fake_client_factory(host: str, port: int, **_kwargs: object) -> "_FakeClient":
        client = _FakeClient(host, port)
        clients.append(client)
        return client

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        fake_start_engine_stream,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        fake_client_factory,
        raising=False,
    )

    start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
    stop_cls = bpy.utils.registered_class("POSECAP_OT_StopStream")

    try:
        assert start_cls().execute(context) == {"FINISHED"}

        assert settings.lifecycle_state == "STARTING"
        assert settings.status_message == "Starting"
        assert commands == [
            (
                "posecap-engine",
                "live",
                "--pear-root",
                "C:/PEAR",
                "--camera-index",
                "4",
                "--parent-pid",
                str(os.getpid()),
            )
        ]
        assert clients[0].endpoint == ("127.0.0.1", 42321)
        assert clients[0].started
        assert len(bpy.app.timers.registered) == 1

        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0

        assert settings.lifecycle_state == "STREAMING"
        assert settings.status_message == "Streaming"

        assert stop_cls().execute(context) == {"FINISHED"}

        assert settings.lifecycle_state == "STOPPED"
        assert settings.status_message == "Stopped"
        assert not bpy.app.timers.registered
        assert clients[0].closed
        assert engine.stopped
    finally:
        unregister_blender_ui(bpy)


def test_start_stream_uses_addon_preferences_when_scene_runtime_fields_are_empty(
    monkeypatch,
) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.camera_index = 4
    preferences = _FakeAddonPreferences(
        pear_root="C:/PEAR",
        engine_executable="C:/PoseCap/posecap-engine.exe",
    )
    context = _FakeContext(settings, addon_preferences=preferences)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []
    commands: list[tuple[str, ...]] = []

    def fake_start_engine_stream(command):
        commands.append(tuple(command))
        return engine

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        fake_start_engine_stream,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}

        assert commands == [
            (
                "C:/PoseCap/posecap-engine.exe",
                "live",
                "--pear-root",
                "C:/PEAR",
                "--camera-index",
                "4",
                "--parent-pid",
                str(os.getpid()),
            )
        ]
        assert clients[0].started
    finally:
        unregister_blender_ui(bpy)


def test_start_stream_configures_apply_time_instrumentation(monkeypatch, tmp_path) -> None:
    bpy = _FakeBpy()
    bpy.app.tempdir = str(tmp_path)
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []
    log_paths: list[Path] = []
    instrumentation_loggers: list[object] = []
    logger = object()

    def fake_configure_addon_logging(log_path: Path) -> object:
        log_paths.append(log_path)
        return logger

    def fake_instrumentation(*, logger: object) -> object:
        instrumentation_loggers.append(logger)
        return object()

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "configure_addon_logging",
        fake_configure_addon_logging,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "ApplyTimeInstrumentation",
        fake_instrumentation,
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}

        assert log_paths == [tmp_path / "posecap-addon.log"]
        assert instrumentation_loggers == [logger]
    finally:
        unregister_blender_ui(bpy)


def test_starting_stream_stops_from_timer_when_client_reports_connect_error(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}
        clients[0].error = TimeoutError("timed out connecting")

        assert bpy.app.timers.registered[0]() is None

        assert settings.lifecycle_state == "STOPPED"
        assert settings.status_message == "Connect failed: timed out connecting"
        assert clients[0].closed
        assert engine.stopped
    finally:
        unregister_blender_ui(bpy)


def test_start_stream_real_client_timeout_stops_engine_process(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    unused_port = _unused_localhost_port()
    script = (
        "import json, time; "
        "print(json.dumps("
        f"{{'event': 'listening', 'host': '127.0.0.1', 'port': {unused_port}}}"
        "), flush=True); "
        "time.sleep(30)"
    )
    command = (sys.executable, "-c", script)
    engines: list[EngineProcess] = []
    clients: list[TcpPoseStreamClient] = []
    start_engine_stream = posecap_addon.panels.start_engine_stream

    def capture_engine(_command: tuple[str, ...]) -> EngineProcess:
        engine = start_engine_stream(command, startup_timeout_seconds=2.0)
        engines.append(engine)
        return engine

    def real_timeout_client(host: str, port: int, **_kwargs: object) -> TcpPoseStreamClient:
        client = TcpPoseStreamClient(
            host,
            port,
            connect_timeout_seconds=0.15,
            retry_interval_seconds=0.01,
        )
        clients.append(client)
        return client

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        capture_engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        real_timeout_client,
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}

        assert settings.lifecycle_state == "STARTING"
        assert len(engines) == 1
        assert engines[0].running
        assert len(clients) == 1
        assert clients[0].connection_state in {"CONNECTING", "STOPPED"}

        assert _run_timer_until_stopped(bpy)

        assert settings.lifecycle_state == "STOPPED"
        assert settings.status_message.startswith("Connect failed: timed out connecting")
        assert clients[0].connection_state == "STOPPED"
        assert not engines[0].running
    finally:
        for engine in engines:
            engine.stop(timeout_seconds=1.0)
        unregister_blender_ui(bpy)


def test_streaming_socket_drop_shows_reconnecting_until_next_frame(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STREAMING"

        clients[0].connection_state = "RECONNECTING"
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "RECONNECTING"
        assert settings.status_message == "Reconnecting"

        clients[0].connection_state = "CONNECTED"
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STREAMING"
        assert settings.status_message == "Streaming"
    finally:
        unregister_blender_ui(bpy)


def test_streaming_socket_drop_does_not_resume_from_queued_stale_frame(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STREAMING"

        clients[0].connection_state = "RECONNECTING"
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 2, 100.5, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0

        assert settings.lifecycle_state == "RECONNECTING"
        assert settings.status_message == "Reconnecting"
    finally:
        unregister_blender_ui(bpy)


def test_streaming_engine_death_stops_with_reported_reason(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STREAMING"

        engine.running = False
        assert bpy.app.timers.registered[0]() is None

        assert settings.lifecycle_state == "STOPPED"
        assert settings.status_message == "Engine process exited"
        assert clients[0].closed
        assert engine.stopped
    finally:
        unregister_blender_ui(bpy)


def test_streaming_invalid_armature_warns_and_reselected_target_resumes(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.target_armature = _RemovedArmature()
    context = _FakeContext(settings)
    engine = _FakeEngine()
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "ok", _payload()))

        assert bpy.app.timers.registered[0]() == 1.0 / 60.0

        assert settings.lifecycle_state == "WARNING"
        assert settings.status_message == "target armature is unavailable"

        replacement = _FakeArmature(["pelvis"])
        settings.target_armature = replacement
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 2, 100.5, "ok", _payload()))

        assert bpy.app.timers.registered[0]() == 1.0 / 60.0

        assert settings.lifecycle_state == "STREAMING"
        assert settings.status_message == "Streaming"
        assert replacement.pose.bones["pelvis"].rotation_mode == "QUATERNION"
    finally:
        unregister_blender_ui(bpy)


def test_stop_stream_terminates_engine_process_and_removes_pid(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        shell=False,
    )
    engine = EngineProcess(
        process=process,
        endpoint=EngineEndpoint(host="127.0.0.1", port=42321),
        command=(sys.executable, "-c", "import time; time.sleep(30)"),
    )
    clients: list[_FakeClient] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: clients.append(_FakeClient(host, port)) or clients[-1],
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        stop_cls = bpy.utils.registered_class("POSECAP_OT_StopStream")
        assert start_cls().execute(context) == {"FINISHED"}
        pid = engine.pid
        assert _pid_is_listed(pid)

        assert stop_cls().execute(context) == {"FINISHED"}

        assert settings.lifecycle_state == "STOPPED"
        assert settings.status_message == "Stopped"
        assert process.poll() is not None
        assert not _pid_is_listed(pid)
        assert clients[0].closed
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        unregister_blender_ui(bpy)


class _Settings:
    lifecycle_state: LifecycleState
    status_message: str
    target_armature: object | None

    def __init__(self, *, lifecycle_state: LifecycleState, status_message: str = "") -> None:
        self.lifecycle_state = lifecycle_state
        self.status_message = status_message
        self.target_armature = None
        self.camera_index = 0
        self.pear_root = ""
        self.record_live_mocap = False
        self.apply_orientation_fix = True
        self.world_position_experimental = False


class _FakeLayout:
    def __init__(
        self,
        *,
        enabled: bool = True,
        operators: list[tuple[str, bool]] | None = None,
        properties: list[tuple[str, bool]] | None = None,
        labels: list[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self._operators = [] if operators is None else operators
        self._properties = [] if properties is None else properties
        self._labels = [] if labels is None else labels

    def row(self, *, align: bool = False) -> "_FakeLayout":
        return _FakeLayout(
            enabled=self.enabled,
            operators=self._operators,
            properties=self._properties,
            labels=self._labels,
        )

    def column(self) -> "_FakeLayout":
        return self.row()

    def box(self) -> "_FakeLayout":
        return self.row()

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self._labels.append(text)

    def prop(self, _data: object, property_name: str, **_kwargs: object) -> None:
        self._properties.append((property_name, self.enabled))

    def operator(self, operator_id: str, *, text: str = "", icon: str = "NONE") -> None:
        self._operators.append((operator_id, self.enabled))

    def enabled_for_operator(self, operator_id: str) -> bool:
        return self._enabled_for(operator_id, self._operators)

    def enabled_for_property(self, property_name: str) -> bool:
        return self._enabled_for(property_name, self._properties)

    def has_property(self, property_name: str) -> bool:
        return any(name == property_name for name, _enabled in self._properties)

    def has_label(self, text: str) -> bool:
        return text in self._labels

    @staticmethod
    def _enabled_for(name: str, values: list[tuple[str, bool]]) -> bool:
        matches = [enabled for value_name, enabled in values if value_name == name]
        if len(matches) != 1:
            raise AssertionError(f"expected one entry for {name}, got {matches}")
        return matches[0]


class _FakeContext:
    def __init__(
        self,
        settings: _Settings,
        *,
        addon_preferences: "_FakeAddonPreferences | None" = None,
    ) -> None:
        self.scene = _FakeScene(settings)
        self.window_manager = _FakeWindowManager()
        self.preferences = _FakePreferences(addon_preferences)


class _FakeScene:
    def __init__(self, settings: _Settings) -> None:
        self.posecap = settings


class _FakeWindowManager:
    windows: list[object] = []


class _FakeBpy:
    def __init__(self) -> None:
        self.types = _FakeBpyTypes()
        self.props = _FakeBpyProps()
        self.utils = _FakeBpyUtils()
        self.app = _FakeBpyApp()


class _FakeBpyTypes:
    class AddonPreferences:
        pass

    class PropertyGroup:
        pass

    class Panel:
        pass

    class Operator:
        pass

    class Object:
        pass

    class Scene:
        pass


class _FakeBpyProps:
    def EnumProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("EnumProperty", kwargs)

    def StringProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("StringProperty", kwargs)

    def IntProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("IntProperty", kwargs)

    def BoolProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("BoolProperty", kwargs)

    def PointerProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("PointerProperty", kwargs)


class _FakeBpyUtils:
    def __init__(self) -> None:
        self.registered: list[type] = []
        self.unregistered: list[type] = []

    def register_class(self, cls: type) -> None:
        self.registered.append(cls)

    def unregister_class(self, cls: type) -> None:
        self.unregistered.append(cls)

    def registered_class(self, name: str) -> type:
        for cls in self.registered:
            if cls.__name__ == name:
                return cls
        raise AssertionError(f"missing registered class {name}")


class _FakeBpyApp:
    def __init__(self) -> None:
        self.timers = _FakeTimers()
        self.tempdir = ""


class _FakeTimers:
    def __init__(self) -> None:
        self.registered: list[Callable[[], float | None]] = []

    def register(
        self,
        function: Callable[[], float | None],
        *,
        first_interval: float = 0.0,
        persistent: bool = False,
    ) -> None:
        self.registered.append(function)

    def unregister(self, function: Callable[[], float | None]) -> None:
        self.registered.remove(function)

    def is_registered(self, function: Callable[[], float | None]) -> bool:
        return function in self.registered


class _FakeEndpoint:
    host = "127.0.0.1"
    port = 42321


class _FakeEngine:
    endpoint = _FakeEndpoint()

    def __init__(self) -> None:
        self.running = True
        self.stopped = False

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        self.running = False
        self.stopped = True


class _FakeClient:
    def __init__(self, host: str, port: int) -> None:
        self.endpoint = (host, port)
        self.frames: list[PoseFrame] = []
        self.error: BaseException | None = None
        self.connection_state = "CONNECTED"
        self.started = False
        self.closed = False

    def start(self) -> None:
        self.started = True

    def latest(self) -> PoseFrame | None:
        if not self.frames:
            return None
        return self.frames.pop(0)

    def close(self, *, timeout_seconds: float = 2.0) -> None:
        self.closed = True


class _FakeAddonPreferences:
    def __init__(self, *, pear_root: str, engine_executable: str) -> None:
        self.pear_root = pear_root
        self.engine_executable = engine_executable


class _FakePreferences:
    def __init__(self, addon_preferences: _FakeAddonPreferences | None) -> None:
        self.addons = {}
        if addon_preferences is not None:
            self.addons[ADDON_ID] = _FakeAddon(addon_preferences)


class _FakeAddon:
    def __init__(self, preferences: _FakeAddonPreferences) -> None:
        self.preferences = preferences


class _RemovedArmature:
    @property
    def pose(self):
        raise ReferenceError("StructRNA of type Object has been removed")


class _FakeArmature:
    def __init__(self, bone_names: list[str]) -> None:
        self.pose = _FakePose(bone_names)


class _FakePose:
    def __init__(self, bone_names: list[str]) -> None:
        self.bones = _FakeBones(bone_names)


class _FakeBones:
    def __init__(self, bone_names: list[str]) -> None:
        self._bones = {name: _FakeBone(name) for name in bone_names}

    def __iter__(self):
        return iter(self._bones.values())

    def __getitem__(self, name: str):
        return self._bones[name]

    def get(self, name: str):
        return self._bones.get(name)


class _FakeBone:
    def __init__(self, name: str) -> None:
        self.name = name
        self.rotation_mode = "XYZ"
        self.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        self.keyframes: list[str] = []

    def keyframe_insert(self, *, data_path: str) -> None:
        self.keyframes.append(data_path)


def _payload() -> PosePayload:
    return PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_BODY_JOINTS)],
        left_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        right_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0 for _ in range(NUM_BETAS)],
        expression=[0.0 for _ in range(NUM_EXPRESSION)],
        transl=[0.0, 0.0, 0.0],
    )


def _pid_is_listed(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return completed.returncode == 0 and str(pid) in completed.stdout
    completed = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid="],
        check=False,
        capture_output=True,
        text=True,
        timeout=5.0,
    )
    return completed.returncode == 0 and completed.stdout.strip() == str(pid)


def _unused_localhost_port() -> int:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", 0))
        address = probe.getsockname()
        if not isinstance(address, tuple) or len(address) < 2:
            raise AssertionError(f"unexpected probe address: {address!r}")
        return int(address[1])
    finally:
        probe.close()


def _run_timer_until_stopped(bpy: _FakeBpy) -> bool:
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not bpy.app.timers.registered:
            return True
        if bpy.app.timers.registered[0]() is None:
            return True
        time.sleep(0.02)
    return False
