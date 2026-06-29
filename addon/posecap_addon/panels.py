"""Blender UI panel adapters for PoseCap live streaming."""

import importlib
import os
import tempfile
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .engine_process import start_engine_stream
from .instrumentation import ApplyTimeInstrumentation, configure_addon_logging
from .stream_client import TcpPoseStreamClient
from .ui_state import LIFECYCLE_STATE_ITEMS, LifecycleState, lifecycle_controls

SCENE_PROPERTY_NAME = "posecap"

_REGISTERED_CLASSES: tuple[type[Any], ...] = ()
_ACTIVE_SESSION: "_LiveStreamSession | None" = None
_RECONNECTABLE_STATES = frozenset({"STREAMING", "RECORDING"})


class _LiveStreamSettings(Protocol):
    lifecycle_state: LifecycleState
    status_message: str
    target_armature: Any
    camera_index: int
    pear_root: str
    apply_orientation_fix: bool
    record_live_mocap: bool


def draw_live_stream_panel(layout: Any, settings: _LiveStreamSettings) -> None:
    """Draw the live-stream controls from the current lifecycle state."""
    controls = lifecycle_controls(
        settings.lifecycle_state,
        status_message=settings.status_message,
    )

    box = layout.box()
    box.label(text=controls.status_text, icon="INFO")

    column = layout.column()
    column.prop(settings, "target_armature")
    column.prop(settings, "camera_index")
    column.prop(settings, "pear_root")
    column.prop(settings, "apply_orientation_fix")

    actions = layout.row(align=True)
    start = actions.row()
    start.enabled = controls.can_start
    start.operator("posecap.start_stream", text="Start Stream", icon="PLAY")

    stop = actions.row()
    stop.enabled = controls.can_stop
    stop.operator("posecap.stop_stream", text="Stop Stream", icon="PAUSE")

    record = layout.row()
    record.enabled = controls.can_record
    record.prop(settings, "record_live_mocap", toggle=True)


def register() -> None:
    """Register the Blender UI classes with the runtime bpy module."""
    register_blender_ui(importlib.import_module("bpy"))


def unregister() -> None:
    """Unregister the Blender UI classes from the runtime bpy module."""
    unregister_blender_ui(importlib.import_module("bpy"))


def register_blender_ui(bpy_module: Any) -> None:
    """Register PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    if _REGISTERED_CLASSES:
        return

    classes = _build_blender_classes(bpy_module)
    for cls in classes:
        bpy_module.utils.register_class(cls)
    setattr(
        bpy_module.types.Scene,
        SCENE_PROPERTY_NAME,
        bpy_module.props.PointerProperty(type=classes[0]),
    )
    _REGISTERED_CLASSES = classes


def unregister_blender_ui(bpy_module: Any) -> None:
    """Unregister PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    _stop_active_session(bpy_module)
    if hasattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME):
        delattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME)
    if not _REGISTERED_CLASSES:
        return
    for cls in reversed(_REGISTERED_CLASSES):
        bpy_module.utils.unregister_class(cls)
    _REGISTERED_CLASSES = ()


def _build_blender_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    class POSECAP_PG_LiveStreamSettings(bpy_module.types.PropertyGroup):
        __slots__ = ()

    POSECAP_PG_LiveStreamSettings.__annotations__ = {
        "lifecycle_state": bpy_module.props.EnumProperty(
            name="State",
            description="Live stream lifecycle state",
            items=LIFECYCLE_STATE_ITEMS,
            default="STOPPED",
        ),
        "status_message": bpy_module.props.StringProperty(
            name="Status",
            description="Last stream lifecycle message",
            default="",
        ),
        "target_armature": bpy_module.props.PointerProperty(
            name="Target Armature",
            description="SMPL-X armature that receives live poses",
            type=bpy_module.types.Object,
            poll=_is_armature_object,
        ),
        "camera_index": bpy_module.props.IntProperty(
            name="Camera",
            description="Engine capture device index",
            default=0,
            min=0,
        ),
        "pear_root": bpy_module.props.StringProperty(
            name="PEAR Root",
            description="External PEAR checkout path",
            default="",
            subtype="DIR_PATH",
        ),
        "apply_orientation_fix": bpy_module.props.BoolProperty(
            name="PEAR Orientation Fix",
            description="Apply PoseCap's PEAR-to-SMPL-X orientation correction",
            default=True,
        ),
        "record_live_mocap": bpy_module.props.BoolProperty(
            name="Record Live MoCap",
            description="Insert keyframes for applied stream frames",
            default=False,
        ),
    }

    class POSECAP_OT_StartStream(bpy_module.types.Operator):
        bl_idname = "posecap.start_stream"
        bl_label = "Start Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return _settings_from_context(context).lifecycle_state == "STOPPED"

        def execute(self, context: Any) -> set[str]:
            return _start_live_stream(context, bpy_module)

    class POSECAP_OT_StopStream(bpy_module.types.Operator):
        bl_idname = "posecap.stop_stream"
        bl_label = "Stop Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return lifecycle_controls(_settings_from_context(context).lifecycle_state).can_stop

        def execute(self, context: Any) -> set[str]:
            return _stop_live_stream(context, bpy_module)

    class POSECAP_PT_LiveStream(bpy_module.types.Panel):
        bl_label = "PoseCap"
        bl_idname = "POSECAP_PT_live_stream"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "PoseCap"

        def draw(self, context: Any) -> None:
            draw_live_stream_panel(self.layout, _settings_from_context(context))

    return (
        POSECAP_PG_LiveStreamSettings,
        POSECAP_OT_StartStream,
        POSECAP_OT_StopStream,
        POSECAP_PT_LiveStream,
    )


def _settings_from_context(context: Any) -> Any:
    return getattr(context.scene, SCENE_PROPERTY_NAME)


def _is_armature_object(_settings: Any, candidate: Any) -> bool:
    return getattr(candidate, "type", None) == "ARMATURE"


def _start_live_stream(context: Any, bpy_module: Any) -> set[str]:
    global _ACTIVE_SESSION
    settings = _settings_from_context(context)
    _stop_active_session(bpy_module)
    settings.lifecycle_state = "STARTING"
    settings.status_message = "Starting"
    engine = None
    try:
        engine = start_engine_stream(_engine_command(settings))
        client = TcpPoseStreamClient(
            engine.endpoint.host,
            engine.endpoint.port,
        )
        client.start()
        lifecycle_stream = _LifecyclePoseStream(client, settings)
        writer = _LiveTargetArmaturePoseWriter(
            settings,
            redraw=lambda: tag_view3d_redraw(context),
        )
        logger = configure_addon_logging(_addon_log_path(bpy_module))
        timer = PoseApplyTimer(
            lifecycle_stream,
            writer,
            apply_orientation_fix=bool(settings.apply_orientation_fix),
            insert_keyframes=bool(settings.record_live_mocap),
            on_warning=lambda message: _handle_apply_warning(settings, message),
            on_recovery=lambda: _handle_apply_recovery(settings),
            instrumentation=ApplyTimeInstrumentation(logger=logger),
        )
        session = _LiveStreamSession(bpy_module, settings, engine, client, timer)
        bpy_module.app.timers.register(session.timer_callback, first_interval=0.0)
        _ACTIVE_SESSION = session
    except Exception as exc:
        if engine is not None:
            engine.stop(timeout_seconds=1.0)
        settings.lifecycle_state = "STOPPED"
        settings.status_message = f"Start failed: {exc}"
        return {"CANCELLED"}
    return {"FINISHED"}


def _stop_live_stream(context: Any, bpy_module: Any) -> set[str]:
    settings = _settings_from_context(context)
    _stop_active_session(bpy_module)
    settings.lifecycle_state = "STOPPED"
    settings.status_message = "Stopped"
    settings.record_live_mocap = False
    return {"FINISHED"}


def _stop_active_session(bpy_module: Any) -> None:
    global _ACTIVE_SESSION
    session = _ACTIVE_SESSION
    _ACTIVE_SESSION = None
    if session is not None:
        session.stop(unregister_timer=True, bpy_module=bpy_module)


def _engine_command(settings: _LiveStreamSettings) -> tuple[str, ...]:
    pear_root = str(settings.pear_root).strip()
    if pear_root == "":
        raise ValueError("PEAR Root is required")
    return (
        "posecap-engine",
        "live",
        "--pear-root",
        pear_root,
        "--camera-index",
        str(int(settings.camera_index)),
        "--parent-pid",
        str(os.getpid()),
    )


def _handle_apply_warning(settings: _LiveStreamSettings, message: str) -> None:
    settings.lifecycle_state = "WARNING"
    settings.status_message = message


def _handle_apply_recovery(settings: _LiveStreamSettings) -> None:
    if settings.lifecycle_state != "WARNING":
        return
    if bool(settings.record_live_mocap):
        settings.lifecycle_state = "RECORDING"
        settings.status_message = "Recording"
        return
    settings.lifecycle_state = "STREAMING"
    settings.status_message = "Streaming"


def _addon_log_path(bpy_module: Any) -> Path:
    tempdir = str(getattr(bpy_module.app, "tempdir", "")).strip()
    root = Path(tempdir) if tempdir != "" else Path(tempfile.gettempdir())
    return root / "posecap-addon.log"


class _LiveTargetArmaturePoseWriter:
    def __init__(
        self,
        settings: _LiveStreamSettings,
        *,
        redraw: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._redraw = redraw

    def is_valid(self) -> bool:
        return self._writer().is_valid()

    def apply(self, plan: Any, *, insert_keyframes: bool) -> None:
        self._writer().apply(plan, insert_keyframes=insert_keyframes)

    def tag_redraw(self) -> None:
        if self._redraw is not None:
            self._redraw()

    def _writer(self) -> BpyArmaturePoseWriter:
        return BpyArmaturePoseWriter(self._settings.target_armature)


class _LifecyclePoseStream:
    def __init__(self, client: Any, settings: _LiveStreamSettings) -> None:
        self._client = client
        self._settings = settings

    def latest(self) -> Any | None:
        frame = self._client.latest()
        if frame is not None and self._settings.lifecycle_state == "STARTING":
            self._settings.lifecycle_state = "STREAMING"
            self._settings.status_message = "Streaming"
        if (
            frame is not None
            and self._settings.lifecycle_state == "RECONNECTING"
            and getattr(self._client, "connection_state", "CONNECTED") == "CONNECTED"
        ):
            self._settings.lifecycle_state = "STREAMING"
            self._settings.status_message = "Streaming"
        return frame

    def close(self) -> None:
        self._client.close()


class _LiveStreamSession:
    def __init__(
        self,
        bpy_module: Any,
        settings: _LiveStreamSettings,
        engine: Any,
        client: Any,
        timer: PoseApplyTimer,
    ) -> None:
        self._bpy_module = bpy_module
        self._settings = settings
        self._engine = engine
        self._client = client
        self._timer = timer
        self._stopped = False
        self.timer_callback: Callable[[], float | None] = self._tick

    def _tick(self) -> float | None:
        if self._stopped:
            return None
        if not bool(getattr(self._engine, "running", True)):
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            self._settings.lifecycle_state = "STOPPED"
            self._settings.status_message = "Engine process exited"
            return None
        if (
            getattr(self._client, "connection_state", None) == "RECONNECTING"
            and self._settings.lifecycle_state in _RECONNECTABLE_STATES
        ):
            self._settings.lifecycle_state = "RECONNECTING"
            self._settings.status_message = "Reconnecting"
        stream_error = getattr(self._client, "error", None)
        if stream_error is not None:
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            if self._settings.lifecycle_state == "STARTING":
                self._settings.lifecycle_state = "STOPPED"
                self._settings.status_message = f"Connect failed: {stream_error}"
            else:
                self._settings.lifecycle_state = "STOPPED"
                self._settings.status_message = f"Stream stopped: {stream_error}"
            return None
        return self._timer.tick()

    def stop(self, *, unregister_timer: bool, bpy_module: Any) -> None:
        if self._stopped:
            return
        self._stopped = True
        if unregister_timer:
            _unregister_timer(bpy_module, self.timer_callback)
        self._timer.stop()
        self._engine.stop(timeout_seconds=5.0)


def _unregister_timer(bpy_module: Any, callback: Callable[[], float | None]) -> None:
    timers = bpy_module.app.timers
    is_registered = getattr(timers, "is_registered", None)
    if callable(is_registered) and not bool(is_registered(callback)):
        return
    with suppress(ValueError):
        timers.unregister(callback)
