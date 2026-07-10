"""Blender UI panel adapters for PoseCap live streaming."""

import importlib
import logging
import os
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from posecap_core import LimbFilter, PoseSmoother

from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .character_setup_panel import (
    CHARACTER_PRESET_ITEMS,
    build_character_setup_classes,
    draw_character_setup_section,
)
from .engine_process import start_engine_stream
from .instrumentation import ApplyTimeInstrumentation, configure_addon_logging
from .model_setup_panel import (
    active_model_setup_session,
    build_model_setup_classes,
    draw_body_models_section,
    models_missing,
)
from .stream_client import TcpPoseStreamClient
from .ui_state import LIFECYCLE_STATE_ITEMS, LifecycleState, lifecycle_controls

SCENE_PROPERTY_NAME = "posecap"
WM_MODEL_SETUP_PROPERTY_NAME = "posecap_model_setup"
_MANIFEST_ADDON_ID = "posecap"
ADDON_ID = (
    __package__.removesuffix(".posecap_addon")
    if __package__ and __package__ != "posecap_addon"
    else _MANIFEST_ADDON_ID
)

_REGISTERED_CLASSES: tuple[type[Any], ...] = ()
_ACTIVE_SESSION: "_LiveStreamSession | None" = None
_RECONNECTABLE_STATES = frozenset({"STREAMING", "RECORDING"})

# First Start Stream pulls the pinned PEAR pose weight (~2.7 GB) before the
# first frame; without this the panel sits on "Starting" for minutes and a
# non-technical user assumes it hung (Corridor field report, 2026-07-10).
_LONG_START_SECONDS = 10.0
_LONG_START_MESSAGE = (
    "Still starting — this can take a few minutes; the very first run also "
    "downloads the AI model (~2.7 GB)"
)


def _now() -> float:
    return time.monotonic()


class _LiveStreamSettings(Protocol):
    lifecycle_state: LifecycleState
    status_message: str
    target_armature: Any
    camera_index: int
    pear_root: str
    apply_orientation_fix: bool
    world_position_experimental: bool
    pose_smoothing: bool
    show_advanced: bool
    pose_smoothing_min_cutoff: float
    pose_smoothing_beta: float
    record_live_mocap: bool
    detection_confidence: float
    detector_model: str
    capture_width: int
    capture_height: int
    apply_arms: bool
    apply_legs: bool
    apply_torso: bool
    character_preset: str
    character_mapping_json: str


class _AddonPreferences(Protocol):
    pear_root: str
    engine_executable: str


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
    column.prop(settings, "world_position_experimental")
    column.prop(settings, "pose_smoothing")

    # CK2P progressive disclosure: simple by default, fine control on demand
    advanced_header = layout.row()
    advanced_header.prop(settings, "show_advanced", toggle=True)
    if settings.show_advanced:
        advanced = layout.box().column()
        advanced.label(text="Smoothing", icon="SMOOTHCURVE")
        advanced.prop(settings, "pose_smoothing_min_cutoff")
        advanced.prop(settings, "pose_smoothing_beta")
        advanced.label(text="Engine", icon="SETTINGS")
        advanced.prop(settings, "detection_confidence")
        advanced.prop(settings, "detector_model")
        resolution = advanced.row(align=True)
        resolution.prop(settings, "capture_width")
        resolution.prop(settings, "capture_height")
        advanced.label(text="Apply Capture To", icon="FILTER")
        limbs = advanced.row(align=True)
        limbs.prop(settings, "apply_arms", toggle=True)
        limbs.prop(settings, "apply_legs", toggle=True)
        limbs.prop(settings, "apply_torso", toggle=True)

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


def draw_addon_preferences(layout: Any, preferences: _AddonPreferences) -> None:
    """Draw persistent addon defaults."""
    layout.prop(preferences, "pear_root")
    layout.prop(preferences, "engine_executable")


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
    model_setup_group = next(cls for cls in classes if cls.__name__ == "POSECAP_PG_ModelSetup")
    setattr(
        bpy_module.types.WindowManager,
        WM_MODEL_SETUP_PROPERTY_NAME,
        bpy_module.props.PointerProperty(type=model_setup_group),
    )
    _REGISTERED_CLASSES = classes


def unregister_blender_ui(bpy_module: Any) -> None:
    """Unregister PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    _stop_active_session(bpy_module)
    if hasattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME):
        delattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME)
    if hasattr(bpy_module.types.WindowManager, WM_MODEL_SETUP_PROPERTY_NAME):
        delattr(bpy_module.types.WindowManager, WM_MODEL_SETUP_PROPERTY_NAME)
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
        "world_position_experimental": bpy_module.props.BoolProperty(
            name="World Position (Experimental)",
            description=(
                "Move the armature with the estimated camera-space translation, "
                "relative to the first streamed frame. Monocular depth is noisy; "
                "expect drift"
            ),
            default=False,
        ),
        "pose_smoothing": bpy_module.props.BoolProperty(
            name="Pose Smoothing",
            description=(
                "One Euro filter on streamed rotations: suppresses estimator "
                "jitter at rest without lagging fast motion"
            ),
            default=True,
        ),
        "show_advanced": bpy_module.props.BoolProperty(
            name="Advanced",
            description="Show fine-tuning controls; defaults work for most captures",
            default=False,
        ),
        "pose_smoothing_min_cutoff": bpy_module.props.FloatProperty(
            name="Smoothing Calm",
            description=(
                "Min cutoff (Hz): lower = steadier when you hold still, "
                "higher = more responsive but more jitter"
            ),
            default=1.0,
            min=0.1,
            max=10.0,
        ),
        "pose_smoothing_beta": bpy_module.props.FloatProperty(
            name="Smoothing Speed Response",
            description=(
                "Beta: higher = fast moves tracked with less lag, "
                "lower = smoother but laggier on quick motion"
            ),
            default=0.5,
            min=0.0,
            max=5.0,
        ),
        "record_live_mocap": bpy_module.props.BoolProperty(
            name="Record Live MoCap",
            description="Insert keyframes for applied stream frames",
            default=False,
        ),
        "detection_confidence": bpy_module.props.FloatProperty(
            name="Detection Confidence",
            description=(
                "Person-detector confidence threshold: lower finds people in "
                "harder shots, higher rejects false detections"
            ),
            default=0.3,
            min=0.05,
            max=0.95,
        ),
        "detector_model": bpy_module.props.EnumProperty(
            name="Detector",
            description="Person-detector size: speed versus detection quality",
            items=(
                ("yolov8n", "Fastest", "Smallest detector; lowest quality"),
                ("yolov8s", "Balanced (30 FPS)", "Default; reaches the 30 FPS budget"),
                ("yolov8m", "High Quality", "Bigger detector; slower"),
                ("yolov8x", "Max Quality", "Largest detector; slowest"),
            ),
            default="yolov8s",
        ),
        "capture_width": bpy_module.props.IntProperty(
            name="Capture Width",
            description="Webcam capture width in pixels",
            default=1280,
            min=320,
            max=3840,
        ),
        "capture_height": bpy_module.props.IntProperty(
            name="Capture Height",
            description="Webcam capture height in pixels",
            default=720,
            min=240,
            max=2160,
        ),
        "apply_arms": bpy_module.props.BoolProperty(
            name="Arms",
            description="Apply captured arm and hand motion",
            default=True,
        ),
        "apply_legs": bpy_module.props.BoolProperty(
            name="Legs",
            description="Apply captured leg and foot motion",
            default=True,
        ),
        "apply_torso": bpy_module.props.BoolProperty(
            name="Torso",
            description="Apply captured spine, neck and head motion",
            default=True,
        ),
        "character_preset": bpy_module.props.EnumProperty(
            name="Skeleton",
            description="Skeleton family of the character to convert",
            items=CHARACTER_PRESET_ITEMS,
            default="AUTO",
        ),
        "character_mapping_json": bpy_module.props.StringProperty(
            name="Mapping File",
            description="JSON file mapping SMPL-X joint names to bone names",
            default="",
            subtype="FILE_PATH",
        ),
    }

    class POSECAP_AP_AddonPreferences(bpy_module.types.AddonPreferences):
        __slots__ = ()

        bl_idname = ADDON_ID
        bl_label = "PoseCap"

        def draw(self, _context: Any) -> None:
            draw_addon_preferences(self.layout, self)

    POSECAP_AP_AddonPreferences.__annotations__ = {
        "pear_root": bpy_module.props.StringProperty(
            name="Default PEAR Root",
            description="Default external PEAR checkout path for new live streams",
            default="",
            subtype="DIR_PATH",
        ),
        "engine_executable": bpy_module.props.StringProperty(
            name="Engine Executable",
            description="Command or absolute path used to launch the PoseCap engine",
            default="posecap-engine",
            subtype="FILE_PATH",
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
            _draw_main_panel(self.layout, context)

    class POSECAP_PG_ModelSetup(bpy_module.types.PropertyGroup):
        __slots__ = ()

    POSECAP_PG_ModelSetup.__annotations__ = {
        # WindowManager properties are never saved into .blend files, and the
        # password field is cleared as soon as the download starts.
        "mpi_email": bpy_module.props.StringProperty(
            name="Email",
            description="Email of your account on the official model sites",
            default="",
        ),
        "mpi_password": bpy_module.props.StringProperty(
            name="Password",
            description=(
                "Password of your account on the official model sites — "
                "used in memory only, never saved or logged"
            ),
            default="",
            subtype="PASSWORD",
        ),
        "status": bpy_module.props.StringProperty(
            name="Status",
            description="Current model setup status",
            default="",
        ),
    }

    setup_operator_classes = build_model_setup_classes(bpy_module)
    character_operator_classes = build_character_setup_classes(bpy_module)

    return (
        POSECAP_PG_LiveStreamSettings,
        POSECAP_PG_ModelSetup,
        POSECAP_AP_AddonPreferences,
        POSECAP_OT_StartStream,
        POSECAP_OT_StopStream,
        *setup_operator_classes,
        *character_operator_classes,
        POSECAP_PT_LiveStream,
    )


def _draw_main_panel(layout: Any, context: Any) -> None:
    settings = _settings_from_context(context)
    wm_group = getattr(context.window_manager, WM_MODEL_SETUP_PROPERTY_NAME, None)
    if wm_group is not None:
        preferences = _addon_preferences(context)
        pear_root = _first_nonempty(settings.pear_root, getattr(preferences, "pear_root", ""))
        draw_body_models_section(
            layout,
            wm_group,
            models_missing=models_missing(pear_root),
            session=active_model_setup_session(),
        )
    draw_live_stream_panel(layout, settings)
    draw_character_setup_section(layout, settings)


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
        preferences = _addon_preferences(context)
        engine = start_engine_stream(_engine_command(settings, preferences))
        client = TcpPoseStreamClient(
            engine.endpoint.host,
            engine.endpoint.port,
        )
        client.start()
        lifecycle_stream = _LifecyclePoseStream(client, settings)
        writer = _LiveTargetArmaturePoseWriter(
            settings,
            # Resolve the context at call time: the operator context captured
            # here dies once execute() returns, and using it from the apply
            # timer raised on the second tick and silently killed the timer
            # (2026-07-10 GUI demo root cause).
            redraw=lambda: tag_view3d_redraw(bpy_module.context),
        )
        logger = configure_addon_logging(_addon_log_path(bpy_module))
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
            apply_orientation_fix=bool(settings.apply_orientation_fix),
            apply_world_position=bool(settings.world_position_experimental),
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


# Mirrors engine POSECAP_PEAR_ROOT_ENV; the addon must not import posecap_engine.
POSECAP_PEAR_ROOT_ENV = "POSECAP_PEAR_ROOT"
# Default install layout (Inno {localappdata}\PoseCap): a fresh install works
# with nothing typed, and this even repairs installs made before this fallback.
_INSTALLER_PEAR_SUBPATH = ("PoseCap", "pear")
_INSTALLER_ENGINE_SUBPATH = ("PoseCap", "runtime", "venv", "Scripts", "posecap-engine.exe")

PathExists = Callable[[Path], bool]


def _engine_command(
    settings: _LiveStreamSettings,
    preferences: _AddonPreferences | None = None,
    *,
    environ: dict[str, str] | None = None,
    path_exists: PathExists | None = None,
) -> tuple[str, ...]:
    env = environ if environ is not None else dict(os.environ)
    exists = path_exists if path_exists is not None else (lambda path: path.exists())
    pear_root = _resolve_pear_root(settings, preferences, env, exists)
    if pear_root == "":
        raise ValueError(
            "PEAR Root is required — set PEAR Root in the PoseCap panel or the addon preferences."
        )
    engine_executable = _resolve_engine_executable(preferences, env, exists)
    return (
        engine_executable,
        "live",
        "--pear-root",
        pear_root,
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
    )


def _resolve_pear_root(
    settings: _LiveStreamSettings,
    preferences: _AddonPreferences | None,
    env: dict[str, str],
    exists: PathExists,
) -> str:
    """Resolve the PEAR checkout, falling back so the user need not type a path.

    Order: explicit panel/preferences value, then the POSECAP_PEAR_ROOT env
    var, then the installer's default location. Empty only when none resolve.
    """
    explicit = _first_nonempty(settings.pear_root, getattr(preferences, "pear_root", ""))
    if explicit != "":
        return explicit
    env_root = env.get(POSECAP_PEAR_ROOT_ENV, "").strip()
    if env_root != "" and exists(Path(env_root)):
        return env_root
    installer_root = _installer_path(env, _INSTALLER_PEAR_SUBPATH)
    if installer_root is not None and exists(installer_root):
        return str(installer_root)
    return ""


def _resolve_engine_executable(
    preferences: _AddonPreferences | None,
    env: dict[str, str],
    exists: PathExists,
) -> str:
    """Resolve the engine launcher: an explicit existing path wins, then the
    installer's app-local venv exe (which is not on PATH), then the bare name."""
    candidate = _first_nonempty(getattr(preferences, "engine_executable", ""))
    if candidate != "" and exists(Path(candidate)):
        return candidate
    installer_exe = _installer_path(env, _INSTALLER_ENGINE_SUBPATH)
    if installer_exe is not None and exists(installer_exe):
        return str(installer_exe)
    return candidate if candidate != "" else "posecap-engine"


def _installer_path(env: dict[str, str], subpath: tuple[str, ...]) -> Path | None:
    local_app_data = env.get("LOCALAPPDATA", "").strip()
    if local_app_data == "":
        return None
    return Path(local_app_data, *subpath)


def _format_float(value: Any) -> str:
    return f"{float(value):g}"


def _limb_filter_from(settings: _LiveStreamSettings) -> LimbFilter | None:
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


def _first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value).strip()
        if text != "":
            return text
    return ""


def _addon_preferences(context: Any) -> _AddonPreferences | None:
    preferences = getattr(context, "preferences", None)
    addons = getattr(preferences, "addons", None)
    if addons is None:
        return None
    addon = addons.get(ADDON_ID) if hasattr(addons, "get") else None
    if addon is None:
        return None
    return getattr(addon, "preferences", None)


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
        self._started_at = _now()
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
        try:
            result = self._timer.tick()
        except Exception as exc:
            # bpy silently unregisters a timer whose callback raises; without
            # this the panel keeps saying Streaming over a dead apply loop
            # (2026-07-10 GUI demo finding).
            logging.getLogger("posecap_addon").exception("pose apply tick failed")
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            self._settings.lifecycle_state = "STOPPED"
            self._settings.status_message = f"Apply failed: {exc} (see posecap-addon.log)"
            return None
        self._flag_long_start_if_stalled()
        return result

    def _flag_long_start_if_stalled(self) -> None:
        """Explain the silent ~2.7 GB first-run weight download without faking detection."""
        if self._settings.lifecycle_state != "STARTING":
            return
        if _now() - self._started_at < _LONG_START_SECONDS:
            return
        if self._settings.status_message == _LONG_START_MESSAGE:
            return
        self._settings.status_message = _LONG_START_MESSAGE
        tag_view3d_redraw(self._bpy_module.context)

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
