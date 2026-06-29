import os
from collections.abc import Callable
from pathlib import Path

import posecap_addon.panels
from posecap_addon.panels import (
    SCENE_PROPERTY_NAME,
    draw_live_stream_panel,
    register_blender_ui,
    unregister_blender_ui,
)
from posecap_addon.ui_state import LifecycleState, lifecycle_controls
from posecap_contracts import SCHEMA_VERSION, PoseFrame


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


def test_blender_ui_registration_adds_scene_state_and_unregisters_cleanly() -> None:
    bpy = _FakeBpy()

    register_blender_ui(bpy)

    assert [cls.__name__ for cls in bpy.utils.registered] == [
        "POSECAP_PG_LiveStreamSettings",
        "POSECAP_OT_StartStream",
        "POSECAP_OT_StopStream",
        "POSECAP_PT_LiveStream",
    ]
    assert getattr(bpy.types.Scene, SCENE_PROPERTY_NAME)[0] == "PointerProperty"

    unregister_blender_ui(bpy)
    unregister_blender_ui(bpy)

    assert not hasattr(bpy.types.Scene, SCENE_PROPERTY_NAME)
    assert [cls.__name__ for cls in bpy.utils.unregistered] == [
        "POSECAP_PT_LiveStream",
        "POSECAP_OT_StopStream",
        "POSECAP_OT_StartStream",
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


class _Settings:
    lifecycle_state: LifecycleState
    status_message: str

    def __init__(self, *, lifecycle_state: LifecycleState, status_message: str = "") -> None:
        self.lifecycle_state = lifecycle_state
        self.status_message = status_message
        self.target_armature = None
        self.camera_index = 0
        self.pear_root = ""
        self.record_live_mocap = False
        self.apply_orientation_fix = True


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
    def __init__(self, settings: _Settings) -> None:
        self.scene = _FakeScene(settings)


class _FakeScene:
    def __init__(self, settings: _Settings) -> None:
        self.posecap = settings


class _FakeBpy:
    def __init__(self) -> None:
        self.types = _FakeBpyTypes()
        self.props = _FakeBpyProps()
        self.utils = _FakeBpyUtils()
        self.app = _FakeBpyApp()


class _FakeBpyTypes:
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
