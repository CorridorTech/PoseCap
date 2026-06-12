"""Per-limb import filters — which bones a pose application may touch.

Semantics ported verbatim from the POC: arms imply wrist plus fingers,
hands imply wrist plus fingers, fingers are matched by name substring.
When any filter is active the pelvis is excluded — global orientation
only applies in unfiltered mode (POC behavior, kept deliberately).
"""

from dataclasses import dataclass

from .skeleton import SMPLX_JOINT_NAMES

_FINGER_SUBSTRINGS = ("index", "middle", "pinky", "ring", "thumb")

_LEFT_FINGERS = frozenset(
    name
    for name in SMPLX_JOINT_NAMES
    if name.startswith("left_") and any(finger in name for finger in _FINGER_SUBSTRINGS)
)
_RIGHT_FINGERS = frozenset(
    name
    for name in SMPLX_JOINT_NAMES
    if name.startswith("right_") and any(finger in name for finger in _FINGER_SUBSTRINGS)
)


@dataclass(frozen=True)
class LimbFilter:
    """One flag per limb group; all False means no filtering (every bone allowed)."""

    arms_left: bool = False
    arms_right: bool = False
    hands_left: bool = False
    hands_right: bool = False
    fingers_left: bool = False
    fingers_right: bool = False
    legs_left: bool = False
    legs_right: bool = False

    def is_active(self) -> bool:
        return any(
            (
                self.arms_left,
                self.arms_right,
                self.hands_left,
                self.hands_right,
                self.fingers_left,
                self.fingers_right,
                self.legs_left,
                self.legs_right,
            )
        )

    def allowed_bones(self) -> frozenset[str] | None:
        """The bone whitelist, or None when no filter is active (all bones allowed)."""
        if not self.is_active():
            return None
        allowed: set[str] = set()
        if self.fingers_left:
            allowed.update(_LEFT_FINGERS)
        if self.fingers_right:
            allowed.update(_RIGHT_FINGERS)
        if self.hands_left:
            allowed.add("left_wrist")
            allowed.update(_LEFT_FINGERS)
        if self.hands_right:
            allowed.add("right_wrist")
            allowed.update(_RIGHT_FINGERS)
        if self.arms_left:
            allowed.update(("left_shoulder", "left_elbow", "left_wrist"))
            allowed.update(_LEFT_FINGERS)
        if self.arms_right:
            allowed.update(("right_shoulder", "right_elbow", "right_wrist"))
            allowed.update(_RIGHT_FINGERS)
        if self.legs_left:
            allowed.update(("left_hip", "left_knee", "left_ankle", "left_foot"))
        if self.legs_right:
            allowed.update(("right_hip", "right_knee", "right_ankle", "right_foot"))
        return frozenset(allowed)
