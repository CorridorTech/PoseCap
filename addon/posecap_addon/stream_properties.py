"""Scene-level PoseCap properties: the live-stream settings PropertyGroup.

The classes are built at runtime against an injected ``bpy_module`` (the
repo-wide builder pattern, see ``model_setup_panel.build_model_setup_classes``)
so unit tests exercise them without Blender. The grouped ``*_properties``
helpers keep each builder under the GUIDELINES section 4 caps while preserving
the exact property declaration order. The file exceeds the ~200-line target
because it is one declarative property table — splitting a single
PropertyGroup's declarations across files would hide its surface, not shrink it.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from posecap_contracts import PoseBackendManifest

from .backend_registry import (
    discover_installed_pose_backends,
    resolve_installed_pose_backend,
)
from .character_setup_panel import CHARACTER_PRESET_ITEMS
from .ui_state import LIFECYCLE_STATE_ITEMS, LifecycleState

SCENE_PROPERTY_NAME = "posecap"
WM_MODEL_SETUP_PROPERTY_NAME = "posecap_model_setup"
_AUTOMATIC_BACKEND_ID = "__automatic__"


class LiveStreamSettings(Protocol):
    """The live-stream settings surface the panel and operators read."""

    lifecycle_state: LifecycleState
    status_message: str
    target_armature: Any
    camera_index: int
    pear_root: str
    apply_orientation_fix: bool
    camera_pitch: float
    world_position_experimental: bool
    pose_smoothing: bool
    show_advanced: bool
    show_support: bool
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
    pose_backend_id: str
    source_kind: str
    video_source: str
    preview_enabled: bool


def settings_from_context(context: Any) -> Any:
    """The scene's PoseCap settings group."""
    return getattr(context.scene, SCENE_PROPERTY_NAME)


def selected_backend_id(settings: LiveStreamSettings) -> str | None:
    """The explicit backend choice, or ``None`` for the automatic option."""
    selected = str(getattr(settings, "pose_backend_id", _AUTOMATIC_BACKEND_ID)).strip()
    if selected in ("", _AUTOMATIC_BACKEND_ID):
        return None
    return selected


def resolve_selected_backend(settings: LiveStreamSettings) -> PoseBackendManifest | None:
    """Resolve the installed backend the settings point at."""
    return resolve_installed_pose_backend(
        dict(os.environ),
        selected_id=selected_backend_id(settings),
    )


def pose_backend_items(_self: Any, _context: Any) -> list[tuple[str, str, str]]:
    """Provide a stable automatic option plus every currently ready backend."""
    catalog = discover_installed_pose_backends(dict(os.environ))
    items = [
        (
            _AUTOMATIC_BACKEND_ID,
            "Automatic",
            "Use the best installed backend for this machine: GPU capture when available",
        )
    ]
    for backend in catalog.ready:
        compatibility = backend.manifest.compatibility
        details = "; ".join(
            (*compatibility.accelerators, compatibility.account, compatibility.license)
        )
        items.append((backend.manifest.id, backend.manifest.display_name, details))
    return items


def _is_armature_object(_settings: Any, candidate: Any) -> bool:
    return getattr(candidate, "type", None) == "ARMATURE"


def build_live_stream_settings_class(bpy_module: Any) -> type[Any]:
    """Build the live-stream settings PropertyGroup against a bpy-like module."""

    class POSECAP_PG_LiveStreamSettings(bpy_module.types.PropertyGroup):
        __slots__ = ()

    POSECAP_PG_LiveStreamSettings.__annotations__ = {
        **_stream_state_properties(bpy_module),
        **_capture_setup_properties(bpy_module),
        **_smoothing_and_disclosure_properties(bpy_module),
        **_recording_and_detector_properties(bpy_module),
        **_limb_and_character_properties(bpy_module),
        **_source_properties(bpy_module),
    }
    return POSECAP_PG_LiveStreamSettings


def _stream_state_properties(bpy_module: Any) -> dict[str, Any]:
    return {
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
        "pose_backend_id": bpy_module.props.EnumProperty(
            name="Pose Backend",
            description="Installed capture backend; Automatic prefers GPU capture",
            items=pose_backend_items,
        ),
    }


def _capture_setup_properties(bpy_module: Any) -> dict[str, Any]:
    return {
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
        "camera_pitch": bpy_module.props.FloatProperty(
            name="Camera Pitch",
            description=(
                "Capture-camera tilt in degrees, to compensate a non-level camera: "
                "positive = looking down, negative = looking up. 0 for a camera at "
                "the subject's height. Needs PEAR Orientation Fix on"
            ),
            default=0.0,
            min=-90.0,
            max=90.0,
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
    }


def _smoothing_and_disclosure_properties(bpy_module: Any) -> dict[str, Any]:
    return {
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
        "show_support": bpy_module.props.BoolProperty(
            name="Help & Support",
            description="Show version, installation health, logs, and support tools",
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
    }


def _recording_and_detector_properties(bpy_module: Any) -> dict[str, Any]:
    return {
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
    }


def _limb_and_character_properties(bpy_module: Any) -> dict[str, Any]:
    return {
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


def _source_properties(bpy_module: Any) -> dict[str, Any]:
    return {
        "source_kind": bpy_module.props.EnumProperty(
            name="Source",
            description="Where capture comes from: a webcam or a recorded video file",
            items=(
                ("CAMERA", "Camera", "Live webcam"),
                ("VIDEO", "Video File", "A recorded video — a virtual camera for testing"),
            ),
            default="CAMERA",
        ),
        "video_source": bpy_module.props.StringProperty(
            name="Video File",
            description="Recorded video that drives capture when Source is Video File",
            default="",
            subtype="FILE_PATH",
        ),
        "preview_enabled": bpy_module.props.BoolProperty(
            name="Show Preview Window",
            description="Open a separate window showing the live camera/video while streaming",
            default=False,
        ),
    }


def build_model_setup_property_group(bpy_module: Any) -> type[Any]:
    """Build the WindowManager-scoped model-setup PropertyGroup."""

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
    return POSECAP_PG_ModelSetup
