"""Pure lifecycle state model for the addon UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LifecycleState = Literal[
    "STOPPED",
    "STARTING",
    "STREAMING",
    "RECORDING",
    "RECONNECTING",
    "WARNING",
]

LIFECYCLE_STATE_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("STOPPED", "Stopped", "No active pose stream"),
    ("STARTING", "Starting", "Engine process or TCP connection is starting"),
    ("STREAMING", "Streaming", "Pose stream is applying frames"),
    ("RECORDING", "Recording", "Pose stream is inserting keyframes"),
    ("RECONNECTING", "Reconnecting", "TCP stream is reconnecting"),
    ("WARNING", "Warning", "Stream is waiting for a recoverable user action"),
)

_STREAM_ACTIVE_STATES = frozenset({"STARTING", "STREAMING", "RECORDING", "RECONNECTING", "WARNING"})
_RECORDABLE_STATES = frozenset({"STREAMING", "RECORDING"})


@dataclass(frozen=True)
class LifecycleControls:
    """Button and status affordances derived from the stream lifecycle state."""

    state: LifecycleState
    label: str
    status_text: str
    can_start: bool
    can_stop: bool
    can_record: bool
    is_recording: bool


def lifecycle_controls(
    state: LifecycleState,
    *,
    status_message: str = "",
) -> LifecycleControls:
    """Return the UI affordances for a lifecycle state."""
    label = _label_for_state(state)
    return LifecycleControls(
        state=state,
        label=label,
        status_text=status_message or label,
        can_start=state == "STOPPED",
        can_stop=state in _STREAM_ACTIVE_STATES,
        can_record=state in _RECORDABLE_STATES,
        is_recording=state == "RECORDING",
    )


def _label_for_state(state: LifecycleState) -> str:
    for identifier, label, _description in LIFECYCLE_STATE_ITEMS:
        if identifier == state:
            return label
    return "Stopped"
