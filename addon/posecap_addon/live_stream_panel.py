"""The live-stream controls section of the PoseCap panel."""

from __future__ import annotations

import os
from typing import Any

from .backend_registry import discover_installed_pose_backends, preferred_pose_backend
from .panel_text import DEFAULT_WRAP_CHARS, draw_wrapped_label
from .stream_properties import LiveStreamSettings, selected_backend_id
from .ui_state import LifecycleState, lifecycle_controls


def draw_live_stream_panel(
    layout: Any,
    settings: LiveStreamSettings,
    *,
    capture_ready: bool = True,
    wrap_chars: int = DEFAULT_WRAP_CHARS,
) -> None:
    """Draw the live-stream controls from the current lifecycle state.

    ``capture_ready`` is False until onboarding is complete (models installed +
    a target character): the capture actions stay disabled and a hint points
    back to the checklist, so a new user cannot click into a failure."""
    controls = lifecycle_controls(
        settings.lifecycle_state,
        status_message=settings.status_message,
    )

    box = layout.box()
    visible_status = settings.status_message or (
        "Ready to capture" if capture_ready else "Setup needed"
    )
    status_text, status_icon, status_alert = _status_presentation(
        settings.lifecycle_state,
        visible_status,
        capture_ready=capture_ready,
    )
    box.alert = status_alert
    # The status line carries long messages too (the first-run warmup hint), so
    # it wraps like the rest rather than truncating.
    draw_wrapped_label(box, status_text, chars=wrap_chars, icon=status_icon)

    column = layout.column()
    column.prop(settings, "target_armature")
    _draw_pose_backend_selector(column, settings)
    _draw_source(column, settings)
    column.prop(settings, "apply_orientation_fix")
    column.prop(settings, "world_position_experimental")
    column.prop(settings, "pose_smoothing")

    # CK2P progressive disclosure: simple by default, fine control on demand
    advanced_header = layout.row()
    advanced_header.prop(settings, "show_advanced", toggle=True)
    if settings.show_advanced:
        _draw_advanced_section(layout, settings)

    if not capture_ready:
        draw_wrapped_label(
            layout,
            "Complete the setup steps above to unlock capture.",
            chars=wrap_chars,
            icon="INFO",
        )

    actions = layout.row(align=True)
    start = actions.row()
    # Gate on onboarding too: a disabled Start Stream is the guidance — it points
    # the user back to the checklist instead of failing on missing models.
    start.enabled = controls.can_start and capture_ready
    start.operator("posecap.start_stream", text="Start Stream", icon="PLAY")

    stop = actions.row()
    stop.enabled = controls.can_stop
    stop.operator("posecap.stop_stream", text="Stop Stream", icon="PAUSE")

    _draw_record_control(layout, controls, capture_ready=capture_ready)


def _draw_advanced_section(layout: Any, settings: LiveStreamSettings) -> None:
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
    # Camera Pitch folds into the orientation fix, so it does nothing when
    # that is off — grey it out rather than let it silently no-op.
    camera_pitch_row = advanced.row()
    camera_pitch_row.enabled = bool(settings.apply_orientation_fix)
    camera_pitch_row.prop(settings, "camera_pitch")
    advanced.label(text="Apply Capture To", icon="FILTER")
    limbs = advanced.row(align=True)
    limbs.prop(settings, "apply_arms", toggle=True)
    limbs.prop(settings, "apply_legs", toggle=True)
    limbs.prop(settings, "apply_torso", toggle=True)


def _draw_record_control(layout: Any, controls: Any, *, capture_ready: bool = True) -> None:
    """Record is an operator, not a bare toggle: it must also drive timeline
    playback so keyframes spread across the advancing playhead (spec R6)."""
    row = layout.row()
    row.enabled = controls.can_record and capture_ready
    if controls.is_recording:
        row.operator("posecap.stop_recording", text="Stop Recording", icon="PAUSE")
        return
    row.operator("posecap.start_recording", text="Record Live MoCap", icon="REC")


def _draw_source(column: Any, settings: LiveStreamSettings) -> None:
    """One place to pick the capture source: a webcam or a recorded video file."""
    column.prop(settings, "source_kind", text="Source")
    property_name, label = _source_input(str(settings.source_kind))
    column.prop(settings, property_name, text=label)
    column.prop(settings, "preview_enabled")


def _source_input(source_kind: str) -> tuple[str, str]:
    if source_kind == "VIDEO":
        return "video_source", "Video File"
    return "camera_index", "Camera"


def _draw_pose_backend_selector(column: Any, settings: LiveStreamSettings) -> None:
    """Keep the backend choice in the normal capture panel, not a terminal workflow."""
    column.prop(settings, "pose_backend_id", text="Pose Backend")
    catalog = discover_installed_pose_backends(dict(os.environ))
    if not catalog.ready and not catalog.issues:
        column.label(text="No Pose Backend is installed.", icon="ERROR")
        column.label(text="Run the PoseCap installer or its Repair option.")
    if len(catalog.ready) > 1 and selected_backend_id(settings) is None:
        # Automatic resolves on its own (task 0038); name the pick so the
        # choice is visible rather than hidden behind the word "Automatic".
        automatic = preferred_pose_backend(catalog)
        column.label(text=f"Automatic uses {automatic.display_name}.", icon="INFO")
    for issue in catalog.issues:
        column.label(text=f"Unavailable Pose Backend: {issue.reason}", icon="ERROR")


def _status_presentation(
    lifecycle_state: LifecycleState,
    status_text: str,
    *,
    capture_ready: bool,
) -> tuple[str, str, bool]:
    """Return concise text, semantic icon, and alert styling for the status card."""
    lowered = status_text.casefold()
    if any(marker in lowered for marker in ("failed", "exited", "could not", "stopped:")):
        return status_text, "ERROR", True
    if lifecycle_state in {"WARNING", "RECONNECTING"}:
        return status_text, "ERROR", True
    if lifecycle_state == "STOPPED" and not status_text.strip():
        return ("Ready to capture" if capture_ready else "Setup needed"), "INFO", False
    if lifecycle_state == "STOPPED" and status_text == "Stopped":
        return "Capture stopped", "CHECKMARK", False
    if lifecycle_state in {"STREAMING", "RECORDING"}:
        return status_text, "CHECKMARK", False
    if lifecycle_state == "STARTING":
        return status_text, "TIME", False
    return status_text, "INFO", False
