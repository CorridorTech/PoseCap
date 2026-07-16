"""Start/Stop Stream operators and the engine launch that backs them."""

from __future__ import annotations

import math
import os
from typing import Any

from posecap_contracts import PoseBackendManifest
from posecap_core import LimbFilter, PoseSmoother

from .apply_timer import PoseApplyTimer, tag_view3d_redraw
from .backend_registry import BackendSelectionError
from .capture_readiness import can_start_stream, capture_setup_issue
from .engine_process import start_engine_stream
from .instrumentation import ApplyTimeInstrumentation, configure_addon_logging
from .pear_root import PathExists, resolve_engine_executable, resolve_pear_root
from .preferences_panel import AddonPreferences, addon_preferences
from .recording import pause_playback
from .stream_client import TcpPoseStreamClient
from .stream_properties import (
    LiveStreamSettings,
    resolve_selected_backend,
    settings_from_context,
)
from .stream_session import (
    LifecyclePoseStream,
    LiveStreamSession,
    LiveTargetArmaturePoseWriter,
    activate_stream_session,
    stop_active_session,
)
from .support import resolve_logs_directory
from .support_panel import addon_log_path
from .ui_state import lifecycle_controls


def build_stream_operator_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Build the Start/Stop Stream operator classes against a bpy-like module."""

    class POSECAP_OT_StartStream(bpy_module.types.Operator):
        bl_idname = "posecap.start_stream"
        bl_label = "Start Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return can_start_stream(context)

        def execute(self, context: Any) -> set[str]:
            return start_live_stream(context, bpy_module)

    class POSECAP_OT_StopStream(bpy_module.types.Operator):
        bl_idname = "posecap.stop_stream"
        bl_label = "Stop Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return lifecycle_controls(settings_from_context(context).lifecycle_state).can_stop

        def execute(self, context: Any) -> set[str]:
            return stop_live_stream(context, bpy_module)

    return (POSECAP_OT_StartStream, POSECAP_OT_StopStream)


def start_live_stream(context: Any, bpy_module: Any) -> set[str]:
    """Launch the engine, connect the stream, and register the apply timer."""
    settings = settings_from_context(context)
    try:
        backend_manifest = resolve_selected_backend(settings)
    except BackendSelectionError as error:
        settings.lifecycle_state = "STOPPED"
        settings.status_message = str(error)
        return {"CANCELLED"}
    setup_issue = capture_setup_issue(context, settings, backend_manifest)
    if setup_issue is not None:
        settings.lifecycle_state = "STOPPED"
        settings.status_message = setup_issue
        return {"CANCELLED"}
    stop_active_session(bpy_module)
    # A fresh stream never inherits recording state: a session that ended
    # abnormally (engine crash, apply error) would otherwise leave the flag set
    # and silently record into the new stream — the POC's exact defect.
    settings.record_live_mocap = False
    settings.lifecycle_state = "STARTING"
    settings.status_message = "Starting"
    engine = None
    logger = None
    try:
        logger = configure_addon_logging(addon_log_path(context, bpy_module))
        preferences = addon_preferences(context)
        engine = start_engine_stream(
            engine_command(settings, preferences, backend_manifest=backend_manifest)
        )
        client = TcpPoseStreamClient(
            engine.endpoint.host,
            engine.endpoint.port,
        )
        client.start()
        lifecycle_stream = LifecyclePoseStream(client, settings)
        writer = LiveTargetArmaturePoseWriter(
            settings,
            # Resolve the context at call time: the operator context captured
            # here dies once execute() returns, and using it from the apply
            # timer raised on the second tick and silently killed the timer
            # (2026-07-10 GUI demo root cause).
            redraw=lambda: tag_view3d_redraw(bpy_module.context),
        )
        timer = PoseApplyTimer(
            lifecycle_stream,
            writer,
            limb_filter=_limb_filter_from(settings),
            smoother=(
                PoseSmoother(
                    min_cutoff=float(settings.pose_smoothing_min_cutoff),
                    beta=float(settings.pose_smoothing_beta),
                )
                if bool(settings.pose_smoothing)
                else None
            ),
            apply_orientation_fix=bool(settings.apply_orientation_fix)
            and (backend_manifest is None or backend_manifest.apply_orientation_fix),
            camera_pitch_radians=math.radians(float(settings.camera_pitch)),
            apply_world_position=bool(settings.world_position_experimental),
            # Live-read: Record is toggled during an active stream, so the timer
            # must see the current flag each tick, not the value at start.
            insert_keyframes=lambda: bool(settings.record_live_mocap),
            on_warning=lambda message: _handle_apply_warning(settings, message),
            on_recovery=lambda: _handle_apply_recovery(settings),
            instrumentation=ApplyTimeInstrumentation(logger=logger),
            supported_capabilities=(
                None if backend_manifest is None else backend_manifest.capabilities
            ),
        )
        session = LiveStreamSession(bpy_module, settings, engine, client, timer)
        bpy_module.app.timers.register(session.timer_callback, first_interval=0.0)
        activate_stream_session(session)
    except Exception as exc:
        if logger is not None:
            logger.exception("capture start failed")
        if engine is not None:
            engine.stop(timeout_seconds=1.0)
        settings.lifecycle_state = "STOPPED"
        settings.status_message = _friendly_start_error(exc)
        return {"CANCELLED"}
    return {"FINISHED"}


def stop_live_stream(context: Any, bpy_module: Any) -> set[str]:
    """Tear down the active session and finalize any in-flight recording."""
    settings = settings_from_context(context)
    stop_active_session(bpy_module)
    settings.lifecycle_state = "STOPPED"
    settings.status_message = "Stopped"
    settings.record_live_mocap = False
    # Stop Stream can be clicked mid-recording (Stop Stream stays enabled while
    # RECORDING): finalize the recording by pausing the timeline the Record
    # operator started, or it plays on over a torn-down stream.
    pause_playback(context, bpy_module)
    return {"FINISHED"}


def engine_command(
    settings: LiveStreamSettings,
    preferences: AddonPreferences | None = None,
    *,
    backend_manifest: PoseBackendManifest | None = None,
    environ: dict[str, str] | None = None,
    path_exists: PathExists | None = None,
) -> tuple[str, ...]:
    """The full engine command line for the current settings and backend."""
    env = environ if environ is not None else dict(os.environ)
    exists = path_exists if path_exists is not None else (lambda path: path.exists())
    command = _base_command(settings, preferences, env, exists, backend_manifest)
    command += [
        "--camera-index",
        str(int(settings.camera_index)),
        "--parent-pid",
        str(os.getpid()),
        "--yolo-threshold",
        _format_float(settings.detection_confidence),
        "--yolo-model",
        str(settings.detector_model),
        "--width",
        str(int(settings.capture_width)),
        "--height",
        str(int(settings.capture_height)),
    ]
    # Video-file source ("virtual camera") only when the user selected it, so a
    # stale path can't hijack a camera run. The engine treats --source as taking
    # precedence over --camera-index.
    if str(getattr(settings, "source_kind", "CAMERA")) == "VIDEO":
        video_source = str(getattr(settings, "video_source", "")).strip()
        if video_source != "":
            # Loop the clip by default: a test source should keep driving the
            # armature instead of ending the stream after one pass.
            command += ["--source", video_source, "--source-loop"]
    if bool(getattr(settings, "preview_enabled", False)):
        command += ["--preview-window"]
    logs = resolve_logs_directory(preferences, env)
    command += ["--log-file", str(logs / "posecap-engine.log")]
    return tuple(command)


def _base_command(
    settings: LiveStreamSettings,
    preferences: AddonPreferences | None,
    env: dict[str, str],
    exists: PathExists,
    backend_manifest: PoseBackendManifest | None,
) -> list[str]:
    """A registered backend brings its own command; PEAR needs resolution."""
    if backend_manifest is not None:
        return list(backend_manifest.command)
    pear_root = resolve_pear_root(settings, preferences, env, exists)
    if pear_root == "":
        raise ValueError(
            "PEAR Root is required — set PEAR Root in the PoseCap panel or the addon preferences."
        )
    engine_executable = resolve_engine_executable(preferences, env, exists)
    return [engine_executable, "live", "--pear-root", pear_root]


def _format_float(value: Any) -> str:
    return f"{float(value):g}"


def _limb_filter_from(settings: LiveStreamSettings) -> LimbFilter | None:
    """Checkbox semantics: all checked = no filtering, none checked = apply nothing."""
    arms = bool(settings.apply_arms)
    legs = bool(settings.apply_legs)
    torso = bool(settings.apply_torso)
    if arms and legs and torso:
        return None
    return LimbFilter(
        arms_left=arms,
        arms_right=arms,
        legs_left=legs,
        legs_right=legs,
        torso=torso,
        apply_nothing=not (arms or legs or torso),
    )


def _handle_apply_warning(settings: LiveStreamSettings, message: str) -> None:
    settings.lifecycle_state = "WARNING"
    settings.status_message = message


def _handle_apply_recovery(settings: LiveStreamSettings) -> None:
    if settings.lifecycle_state != "WARNING":
        return
    if bool(settings.record_live_mocap):
        settings.lifecycle_state = "RECORDING"
        settings.status_message = "Recording"
        return
    settings.lifecycle_state = "STREAMING"
    settings.status_message = "Streaming"


def _friendly_start_error(error: Exception) -> str:
    if isinstance(error, FileNotFoundError):
        return "PoseCap Engine was not found. Run PoseCap Setup (repair), then try again."
    message = str(error).strip()
    if "PEAR Root is required" in message:
        return "PoseCap setup is incomplete. Run PoseCap Setup (repair), then try again."
    if not message:
        return "Capture could not start. Create a Support Bundle so we can help."
    return f"Capture could not start: {message}"
