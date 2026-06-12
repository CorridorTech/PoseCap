"""Pose-application policy: turn a wire payload into bone-level instructions.

The adapter (bpy side) executes the plan verbatim — clear the listed bones,
write the listed quaternions, keyframe KEYFRAME_DATA_PATH when recording.
All decisions (filtering, orientation fix, sign continuity) happen here,
where they are testable without Blender.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from posecap_contracts import PosePayload

from .filters import LimbFilter
from .orientation import flip_global_orient
from .rotation import FloatArray, axis_angle_to_quaternion, make_sign_compatible
from .skeleton import (
    BODY_JOINT_NAMES,
    LEFT_HAND_JOINT_NAMES,
    PELVIS,
    RIGHT_HAND_JOINT_NAMES,
)

KEYFRAME_DATA_PATH = "rotation_quaternion"


@dataclass(frozen=True)
class BoneRotation:
    """quaternion is a read-only array — adapters copy before mutating.

    Plans are safe to keep as the previous_quaternions source for the next
    frame precisely because nothing can mutate them in place.
    """

    bone_name: str
    quaternion: FloatArray


@dataclass(frozen=True)
class PoseApplication:
    """clear_bones is None when every bone resets (unfiltered mode)."""

    clear_bones: frozenset[str] | None
    rotations: tuple[BoneRotation, ...]


def plan_pose_application(
    payload: PosePayload,
    limb_filter: LimbFilter,
    previous_quaternions: Mapping[str, FloatArray] | None = None,
    apply_orientation_fix: bool = True,
) -> PoseApplication:
    """Build the bone-level plan for one frame.

    previous_quaternions maps bone name to the quaternion applied on the
    previous frame; each new quaternion is sign-matched against it to avoid
    360-degree pops (rotation.make_sign_compatible).
    """
    allowed = limb_filter.allowed_bones()
    previous: Mapping[str, FloatArray] = (
        previous_quaternions if previous_quaternions is not None else {}
    )
    rotations: list[BoneRotation] = []

    if allowed is None:
        orient = np.asarray(payload.global_orient, dtype=np.float64)
        if apply_orientation_fix:
            orient = flip_global_orient(orient)
        rotations.append(_bone_rotation(PELVIS, orient, previous))

    for index, name in enumerate(BODY_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(_bone_rotation(name, payload.body_pose[index], previous))

    for index, name in enumerate(LEFT_HAND_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(_bone_rotation(name, payload.left_hand_pose[index], previous))

    for index, name in enumerate(RIGHT_HAND_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(_bone_rotation(name, payload.right_hand_pose[index], previous))

    return PoseApplication(clear_bones=allowed, rotations=tuple(rotations))


def _bone_rotation(
    name: str,
    axis_angle: FloatArray | list[float],
    previous: Mapping[str, FloatArray],
) -> BoneRotation:
    quaternion = axis_angle_to_quaternion(np.asarray(axis_angle, dtype=np.float64))
    reference = previous.get(name)
    if reference is not None:
        quaternion = make_sign_compatible(quaternion, reference)
    quaternion = quaternion.copy()
    quaternion.setflags(write=False)
    return BoneRotation(bone_name=name, quaternion=quaternion)
