import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import posecap_addon.panels
import pytest
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
    assert not layout.enabled_for_operator("posecap.start_recording")
    assert layout.has_property("target_armature")
    assert layout.has_label("Stopped")


def test_capture_actions_disabled_until_onboarding_is_complete() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(lifecycle_state="STOPPED"), capture_ready=False)

    assert not layout.enabled_for_operator("posecap.start_stream"), (
        "Start Stream must be disabled until models + character are ready"
    )
    assert any("Finish Getting Started" in text for text in layout._labels), (
        "a disabled button needs a hint pointing back to the checklist"
    )


def test_capture_actions_enabled_once_onboarding_is_complete() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(lifecycle_state="STOPPED"), capture_ready=True)

    assert layout.enabled_for_operator("posecap.start_stream")
    assert not any("Finish Getting Started" in text for text in layout._labels)


def test_capture_hint_wraps_at_a_narrow_panel_width() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(
        layout, _Settings(lifecycle_state="STOPPED"), capture_ready=False, wrap_chars=18
    )

    # The hint is fully present but spans several labels — nothing truncated.
    hint = [text for text in layout._labels if "Finish" in text or "enable capture" in text]
    assert len(hint) >= 2, "a narrow panel wraps the hint instead of truncating it"
    assert "Finish Getting Started above to enable capture." in " ".join(layout._labels)


def test_panel_wrap_chars_reads_region_width_and_ui_scale() -> None:
    from posecap_addon.panels import _panel_wrap_chars

    def _context(width: int, ui_scale: float = 1.0) -> SimpleNamespace:
        return SimpleNamespace(
            region=SimpleNamespace(width=width),
            preferences=SimpleNamespace(system=SimpleNamespace(ui_scale=ui_scale)),
        )

    assert _panel_wrap_chars(_context(520)) > _panel_wrap_chars(_context(260))
    # A context missing the region or preferences must fall back, never crash.
    assert _panel_wrap_chars(SimpleNamespace()) >= 14


def test_live_stream_panel_offers_record_when_streaming_and_stop_when_recording() -> None:
    streaming = _FakeLayout()
    draw_live_stream_panel(streaming, _Settings(lifecycle_state="STREAMING"))
    assert streaming.enabled_for_operator("posecap.start_recording")
    assert not streaming.has_operator("posecap.stop_recording")

    recording = _FakeLayout()
    draw_live_stream_panel(recording, _Settings(lifecycle_state="RECORDING"))
    assert recording.enabled_for_operator("posecap.stop_recording")
    assert not recording.has_operator("posecap.start_recording")


def test_live_stream_panel_exposes_pose_smoothing_toggle() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(lifecycle_state="STOPPED"))

    assert layout.has_property("pose_smoothing")


def test_advanced_section_collapsed_hides_tuning_and_expanded_shows_it() -> None:
    collapsed = _FakeLayout()
    settings = _Settings(lifecycle_state="STOPPED")
    settings.show_advanced = False
    draw_live_stream_panel(collapsed, settings)
    assert collapsed.has_property("show_advanced")
    assert not collapsed.has_property("pose_smoothing_min_cutoff")
    assert not collapsed.has_property("pose_smoothing_beta")

    expanded = _FakeLayout()
    settings.show_advanced = True
    draw_live_stream_panel(expanded, settings)
    assert expanded.has_property("pose_smoothing_min_cutoff")
    assert expanded.has_property("pose_smoothing_beta")


def test_advanced_section_exposes_engine_settings_and_limb_filters() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    collapsed = _FakeLayout()
    settings.show_advanced = False
    draw_live_stream_panel(collapsed, settings)
    for name in ("detection_confidence", "detector_model", "capture_width", "apply_arms"):
        assert not collapsed.has_property(name)

    expanded = _FakeLayout()
    settings.show_advanced = True
    draw_live_stream_panel(expanded, settings)
    for name in (
        "detection_confidence",
        "detector_model",
        "capture_width",
        "capture_height",
        "apply_arms",
        "apply_legs",
        "apply_torso",
    ):
        assert expanded.has_property(name)


def test_start_stream_passes_engine_settings_from_the_advanced_section(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.detection_confidence = 0.55
    settings.detector_model = "yolov8x"
    settings.capture_width = 1920
    settings.capture_height = 1080
    context = _FakeContext(settings)
    engine = _FakeEngine()
    commands: list[tuple[str, ...]] = []

    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda command: commands.append(tuple(command)) or engine,
        raising=False,
    )
    monkeypatch.setattr(
        posecap_addon.panels,
        "TcpPoseStreamClient",
        lambda host, port, **_kwargs: _FakeClient(host, port),
        raising=False,
    )

    try:
        start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
        assert start_cls().execute(context) == {"FINISHED"}

        command = commands[0]
        assert command[command.index("--yolo-threshold") + 1] == "0.55"
        assert command[command.index("--yolo-model") + 1] == "yolov8x"
        assert command[command.index("--width") + 1] == "1920"
        assert command[command.index("--height") + 1] == "1080"
    finally:
        unregister_blender_ui(bpy)


def test_start_stream_builds_the_limb_filter_from_the_apply_checkboxes(monkeypatch) -> None:
    from posecap_core import LimbFilter

    captured: list[dict[str, object]] = []

    class _RecordingTimer:
        def __init__(self, stream, writer, **kwargs) -> None:
            captured.append(kwargs)
            self._stream = stream

        def tick(self) -> float:
            return 1.0 / 60.0

        def stop(self) -> None:
            self._stream.close()

    def run_start(settings: _Settings) -> None:
        bpy = _FakeBpy()
        register_blender_ui(bpy)
        context = _FakeContext(settings)
        monkeypatch.setattr(
            posecap_addon.panels,
            "start_engine_stream",
            lambda _command: _FakeEngine(),
            raising=False,
        )
        monkeypatch.setattr(
            posecap_addon.panels,
            "TcpPoseStreamClient",
            lambda host, port, **_kwargs: _FakeClient(host, port),
            raising=False,
        )
        monkeypatch.setattr(posecap_addon.panels, "PoseApplyTimer", _RecordingTimer, raising=False)
        try:
            start_cls = bpy.utils.registered_class("POSECAP_OT_StartStream")
            assert start_cls().execute(context) == {"FINISHED"}
        finally:
            unregister_blender_ui(bpy)

    all_on = _Settings(lifecycle_state="STOPPED")
    all_on.pear_root = "C:/PEAR"
    run_start(all_on)
    assert captured[0]["limb_filter"] is None, "all checkboxes on = no filtering"

    torso_off = _Settings(lifecycle_state="STOPPED")
    torso_off.pear_root = "C:/PEAR"
    torso_off.apply_torso = False
    run_start(torso_off)
    limb_filter = captured[1]["limb_filter"]
    assert isinstance(limb_filter, LimbFilter)
    assert limb_filter.is_active()
    allowed = limb_filter.allowed_bones()
    assert allowed is not None
    assert {"left_shoulder", "right_wrist", "left_hip", "right_foot"} <= allowed
    assert "spine1" not in allowed

    # All three unchecked must apply NOTHING, not the whole body — otherwise
    # three empty checkboxes silently drive the entire skeleton.
    all_off = _Settings(lifecycle_state="STOPPED")
    all_off.pear_root = "C:/PEAR"
    all_off.apply_arms = False
    all_off.apply_legs = False
    all_off.apply_torso = False
    run_start(all_off)
    empty_filter = captured[2]["limb_filter"]
    assert isinstance(empty_filter, LimbFilter)
    assert empty_filter.allowed_bones() == frozenset()


def test_addon_preferences_draw_runtime_defaults() -> None:
    layout = _FakeLayout()
    preferences = _FakeAddonPreferences(
        pear_root="C:/PEAR",
        engine_executable="C:/PoseCap/posecap-engine.exe",
    )

    draw_addon_preferences(layout, preferences)

    assert layout.has_property("pear_root")
    assert layout.has_property("engine_executable")


def test_main_panel_shows_getting_started_until_onboarding_is_complete(monkeypatch) -> None:
    # First run: models missing, no armature picked — the checklist is the
    # panel's face and it carries the model-setup wizard call-to-action.
    settings = _Settings(lifecycle_state="STOPPED")
    context = _FakeContext(settings)
    monkeypatch.setattr(posecap_addon.panels, "models_missing", lambda _root: True, raising=False)
    monkeypatch.setattr(
        posecap_addon.panels, "active_model_setup_session", lambda: None, raising=False
    )
    layout = _FakeLayout()

    posecap_addon.panels._draw_main_panel(layout, context)

    assert any("Getting Started" in text for text in layout._labels)
    assert layout.has_operator("posecap.setup_body_models_wizard")
    assert not layout.enabled_for_operator("posecap.start_stream"), (
        "capture stays gated while onboarding is incomplete"
    )


def test_main_panel_collapses_getting_started_when_every_step_is_done(monkeypatch) -> None:
    # Models installed and a valid armature picked: the checklist collapses and
    # the normal stream controls are the panel's face.
    settings = _Settings(lifecycle_state="STOPPED")
    settings.target_armature = SimpleNamespace(type="ARMATURE")
    context = _FakeContext(settings)
    monkeypatch.setattr(posecap_addon.panels, "models_missing", lambda _root: False, raising=False)
    monkeypatch.setattr(
        posecap_addon.panels, "active_model_setup_session", lambda: None, raising=False
    )
    monkeypatch.setattr(
        posecap_addon.panels, "draw_keyframe_manager_section", lambda *a, **k: None, raising=False
    )
    layout = _FakeLayout()

    posecap_addon.panels._draw_main_panel(layout, context)

    assert not any("Getting Started" in text for text in layout._labels)
    assert not layout.has_operator("posecap.setup_body_models_wizard")
    assert layout.enabled_for_operator("posecap.start_stream"), (
        "capture is enabled once every onboarding step is done"
    )


def test_blender_ui_registration_adds_scene_state_and_unregisters_cleanly() -> None:
    bpy = _FakeBpy()

    register_blender_ui(bpy)

    assert [cls.__name__ for cls in bpy.utils.registered] == [
        "POSECAP_PG_LiveStreamSettings",
        "POSECAP_PG_ModelSetup",
        "POSECAP_AP_AddonPreferences",
        "POSECAP_OT_StartStream",
        "POSECAP_OT_StopStream",
        "POSECAP_OT_SetupBodyModels",
        "POSECAP_OT_WatchModelDownloads",
        "POSECAP_OT_SetupBodyModelsWizard",
        "POSECAP_OT_ConvertCharacter",
        "POSECAP_OT_StartRecording",
        "POSECAP_OT_StopRecording",
        "POSECAP_PG_KeyPoseItem",
        "POSECAP_UL_KeyPoseList",
        "POSECAP_OT_AddKeyPose",
        "POSECAP_OT_RemoveKeyPose",
        "POSECAP_OT_ClearKeyPoses",
        "POSECAP_OT_AddAllActiveKeyframes",
        "POSECAP_OT_BakeRetainKeyPoses",
        "POSECAP_PT_LiveStream",
    ]
    preferences_cls = bpy.utils.registered_class("POSECAP_AP_AddonPreferences")
    assert preferences_cls.bl_idname == ADDON_ID
    scene_type: Any = bpy.types.Scene
    assert getattr(scene_type, SCENE_PROPERTY_NAME)[0] == "PointerProperty"
    assert scene_type.posecap_key_poses[0] == "CollectionProperty"
    assert scene_type.posecap_key_poses_index[0] == "IntProperty"
    window_manager_type: Any = bpy.types.WindowManager
    assert window_manager_type.posecap_model_setup[0] == "PointerProperty"

    unregister_blender_ui(bpy)
    unregister_blender_ui(bpy)

    assert not hasattr(bpy.types.Scene, SCENE_PROPERTY_NAME)
    assert not hasattr(bpy.types.Scene, "posecap_key_poses")
    assert not hasattr(bpy.types.Scene, "posecap_key_poses_index")
    assert not hasattr(bpy.types.WindowManager, "posecap_model_setup")
    assert [cls.__name__ for cls in bpy.utils.unregistered] == [
        "POSECAP_PT_LiveStream",
        "POSECAP_OT_BakeRetainKeyPoses",
        "POSECAP_OT_AddAllActiveKeyframes",
        "POSECAP_OT_ClearKeyPoses",
        "POSECAP_OT_RemoveKeyPose",
        "POSECAP_OT_AddKeyPose",
        "POSECAP_UL_KeyPoseList",
        "POSECAP_PG_KeyPoseItem",
        "POSECAP_OT_StopRecording",
        "POSECAP_OT_StartRecording",
        "POSECAP_OT_ConvertCharacter",
        "POSECAP_OT_SetupBodyModelsWizard",
        "POSECAP_OT_WatchModelDownloads",
        "POSECAP_OT_SetupBodyModels",
        "POSECAP_OT_StopStream",
        "POSECAP_OT_StartStream",
        "POSECAP_AP_AddonPreferences",
        "POSECAP_PG_ModelSetup",
        "POSECAP_PG_LiveStreamSettings",
    ]


def test_start_and_stop_operators_own_stream_runtime(monkeypatch) -> None:
    # execute() resolves the engine via real os.environ; hide any installed
    # runtime so this asserts the explicit settings, not the build machine.
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.camera_index = 4
    # A stale flag left by a previous session that ended abnormally must not
    # carry into the new stream and silently record (spec R6 / the POC defect).
    settings.record_live_mocap = True
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
        assert settings.record_live_mocap is False, "start clears any stale record flag"
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
                "--yolo-threshold",
                "0.3",
                "--yolo-model",
                "yolov8s",
                "--width",
                "1280",
                "--height",
                "720",
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


def test_starting_shows_first_run_warmup_hint_after_ten_seconds(monkeypatch) -> None:
    bpy = _FakeBpy()
    register_blender_ui(bpy)
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    context = _FakeContext(settings)
    clients: list[_FakeClient] = []
    clock = {"t": 0.0}

    monkeypatch.setattr(posecap_addon.panels, "_now", lambda: clock["t"], raising=False)
    monkeypatch.setattr(
        posecap_addon.panels,
        "start_engine_stream",
        lambda _command: _FakeEngine(),
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

        # No frame yet, still early: the panel keeps the plain "Starting".
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STARTING"
        assert settings.status_message == "Starting"

        # Past the threshold with still no frame: explain the first-run warmup.
        clock["t"] = 11.0
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STARTING"
        assert "still starting" in settings.status_message.lower()
        assert "warms up" in settings.status_message.lower()

        # A frame finally arrives: normal streaming, the hint is gone.
        clients[0].frames.append(PoseFrame(SCHEMA_VERSION, 1, 100.0, "no_person", None))
        assert bpy.app.timers.registered[0]() == 1.0 / 60.0
        assert settings.lifecycle_state == "STREAMING"
        assert settings.status_message == "Streaming"
    finally:
        unregister_blender_ui(bpy)


def test_engine_command_resolves_pear_root_from_env_var_when_unset() -> None:
    settings = _Settings(lifecycle_state="STOPPED")  # pear_root == ""
    environ = {"POSECAP_PEAR_ROOT": "D:/pear-checkout"}
    existing = {Path("D:/pear-checkout")}

    command = posecap_addon.panels._engine_command(
        settings, None, environ=environ, path_exists=existing.__contains__
    )

    assert command[command.index("--pear-root") + 1] == "D:/pear-checkout"


def test_engine_command_resolves_installer_paths_for_a_fresh_install() -> None:
    # Emmet's case: clean v0.1.2 install, nothing typed, engine pref at default.
    settings = _Settings(lifecycle_state="STOPPED")
    preferences = _FakeAddonPreferences(pear_root="", engine_executable="posecap-engine")
    local = "C:/Users/Corridor/AppData/Local"
    environ = {"LOCALAPPDATA": local}
    installer_pear = Path(local, "PoseCap", "pear")
    installer_exe = Path(local, "PoseCap", "runtime", "venv", "Scripts", "posecap-engine.exe")
    existing = {installer_pear, installer_exe}

    command = posecap_addon.panels._engine_command(
        settings, preferences, environ=environ, path_exists=existing.__contains__
    )

    assert command[command.index("--pear-root") + 1] == str(installer_pear)
    assert command[0] == str(installer_exe)


def test_panel_resolves_installer_pear_root_on_a_fresh_install() -> None:
    # Fresh install, nothing typed: the model-setup section must still detect the
    # installer's pear dir (the same fallback the engine uses), or a new user
    # never sees the model-download guidance and is stuck.
    from types import SimpleNamespace

    settings = _Settings(lifecycle_state="STOPPED")  # pear_root == ""
    preferences = _FakeAddonPreferences(pear_root="", engine_executable="posecap-engine")
    local = "C:/Users/Corridor/AppData/Local"
    installer_pear = Path(local, "PoseCap", "pear")
    context = SimpleNamespace(
        scene=SimpleNamespace(posecap=settings),
        preferences=SimpleNamespace(
            addons={posecap_addon.panels.ADDON_ID: SimpleNamespace(preferences=preferences)}
        ),
    )

    resolved = posecap_addon.panels._panel_pear_root(
        context, environ={"LOCALAPPDATA": local}, path_exists={installer_pear}.__contains__
    )

    assert resolved == str(installer_pear)


def test_engine_command_passes_video_source_only_in_video_mode() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.source_kind = "VIDEO"
    settings.video_source = "C:/clips/dance.mp4"

    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _path: True
    )

    assert command[command.index("--source") + 1] == "C:/clips/dance.mp4"
    # camera-index still present; the engine treats --source as taking precedence.
    assert "--camera-index" in command


def test_engine_command_loops_the_video_source_in_video_mode() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.source_kind = "VIDEO"
    settings.video_source = "C:/clips/dance.mp4"

    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _path: True
    )

    # A test clip should loop rather than end the stream after one pass.
    assert "--source-loop" in command


def test_engine_command_camera_mode_does_not_loop() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.source_kind = "CAMERA"

    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _path: True
    )

    assert "--source-loop" not in command


def test_engine_command_camera_mode_ignores_a_stale_video_path() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"
    settings.source_kind = "CAMERA"
    settings.video_source = "C:/clips/old.mp4"  # left over, must not hijack a camera run

    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _path: True
    )

    assert "--source" not in command


def test_source_selector_camera_mode_shows_index_not_video() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.source_kind = "CAMERA"
    layout = _FakeLayout()
    draw_live_stream_panel(layout, settings)
    assert layout.has_property("source_kind")
    assert layout.has_property("camera_index")
    assert not layout.has_property("video_source")


def test_source_selector_video_mode_shows_path_and_preview_toggle_not_index() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.source_kind = "VIDEO"
    layout = _FakeLayout()
    draw_live_stream_panel(layout, settings)
    assert layout.has_property("source_kind")
    assert layout.has_property("video_source")
    assert layout.has_property("preview_enabled")
    assert not layout.has_property("camera_index")


def test_camera_mode_also_offers_the_preview_toggle() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.source_kind = "CAMERA"
    layout = _FakeLayout()
    draw_live_stream_panel(layout, settings)
    assert layout.has_property("preview_enabled")


def test_engine_command_requests_the_preview_window_only_when_enabled() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "C:/PEAR"

    settings.preview_enabled = True
    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _p: True
    )
    assert "--preview-window" in command

    settings.preview_enabled = False
    command = posecap_addon.panels._engine_command(
        settings, None, environ={}, path_exists=lambda _p: True
    )
    assert "--preview-window" not in command


def test_engine_command_errors_with_where_to_fix_when_nothing_resolves() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    with pytest.raises(ValueError, match="panel or the addon preferences"):
        posecap_addon.panels._engine_command(
            settings, None, environ={}, path_exists=lambda _path: False
        )


def test_engine_command_prefers_explicit_paths_over_fallbacks() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "E:/typed/pear"
    preferences = _FakeAddonPreferences(
        pear_root="", engine_executable="E:/typed/posecap-engine.exe"
    )
    environ = {"POSECAP_PEAR_ROOT": "D:/env-pear", "LOCALAPPDATA": "C:/Users/x/AppData/Local"}
    # Even though the explicit engine path does not "exist", an explicit user
    # value must win over installer discovery.
    existing = {Path("E:/typed/posecap-engine.exe")}

    command = posecap_addon.panels._engine_command(
        settings, preferences, environ=environ, path_exists=existing.__contains__
    )

    assert command[command.index("--pear-root") + 1] == "E:/typed/pear"
    assert command[0] == "E:/typed/posecap-engine.exe"


def test_engine_command_falls_back_to_path_name_for_dev_without_installer() -> None:
    settings = _Settings(lifecycle_state="STOPPED")
    settings.pear_root = "F:/dev/pear"
    preferences = _FakeAddonPreferences(pear_root="", engine_executable="posecap-engine")

    command = posecap_addon.panels._engine_command(
        settings, preferences, environ={}, path_exists=lambda _path: False
    )

    assert command[0] == "posecap-engine"


def test_start_stream_uses_addon_preferences_when_scene_runtime_fields_are_empty(
    monkeypatch,
) -> None:
    # Hide any installed runtime so the installer fallback can't shadow the
    # addon-preference values this test asserts.
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
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
                "--yolo-threshold",
                "0.3",
                "--yolo-model",
                "yolov8s",
                "--width",
                "1280",
                "--height",
                "720",
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


def test_apply_exception_stops_session_and_surfaces_error(monkeypatch) -> None:
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
        session = posecap_addon.panels._ACTIVE_SESSION
        assert session is not None

        def explode() -> float:
            raise RuntimeError("boom in apply")

        monkeypatch.setattr(session._timer, "tick", explode)

        assert bpy.app.timers.registered[0]() is None

        assert settings.lifecycle_state == "STOPPED"
        assert "Apply failed" in settings.status_message
        assert "boom in apply" in settings.status_message
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
        self.camera_pitch = 0.0
        self.world_position_experimental = False
        self.pose_smoothing = True
        self.show_advanced = False
        self.pose_smoothing_min_cutoff = 1.0
        self.pose_smoothing_beta = 0.5
        self.detection_confidence = 0.3
        self.detector_model = "yolov8s"
        self.capture_width = 1280
        self.capture_height = 720
        self.apply_arms = True
        self.apply_legs = True
        self.apply_torso = True
        self.character_preset = "AUTO"
        self.character_mapping_json = ""
        self.source_kind = "CAMERA"
        self.video_source = ""
        self.preview_enabled = False


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

    def has_operator(self, operator_id: str) -> bool:
        return any(name == operator_id for name, _enabled in self._operators)

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
        # Live module context, resolved at call time by the apply-timer redraw
        # (the operator context dies after execute(); see panels start path).
        self.context = _FakeContext(_Settings(lifecycle_state="STOPPED"))


class _FakeBpyTypes:
    class AddonPreferences:
        pass

    class PropertyGroup:
        pass

    class Panel:
        pass

    class Operator:
        def report(self, _levels, _message):
            return None

    class UIList:
        pass

    class Object:
        pass

    class Scene:
        pass

    class WindowManager:
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

    def FloatProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("FloatProperty", kwargs)

    def PointerProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("PointerProperty", kwargs)

    def CollectionProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("CollectionProperty", kwargs)


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
