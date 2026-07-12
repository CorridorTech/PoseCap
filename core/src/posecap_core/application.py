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
from .smoothing import PoseSmoother

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
    """clear_bones is None when every bone resets (unfiltered mode).

    world_offset is a Blender-space armature offset (experimental world
    position) or None when the feature is off or the pelvis is filtered out.
    """

    clear_bones: frozenset[str] | None
    rotations: tuple[BoneRotation, ...]
    world_offset: FloatArray | None = None


def plan_pose_application(
    payload: PosePayload,
    limb_filter: LimbFilter,
    previous_quaternions: Mapping[str, FloatArray] | None = None,
    apply_orientation_fix: bool = True,
    apply_world_position: bool = False,
    translation_origin: FloatArray | None = None,
    smoother: PoseSmoother | None = None,
    captured_at: float = 0.0,
    camera_pitch_radians: float = 0.0,
) -> PoseApplication:
    """Build the bone-level plan for one frame.

    previous_quaternions maps bone name to the quaternion applied on the
    previous frame; each new quaternion is sign-matched against it to avoid
    360-degree pops (rotation.make_sign_compatible).

    smoother, when given, runs each bone's quaternion through the One Euro
    filter keyed by captured_at (the frame's capture timestamp in SECONDS).
    The two travel together: passing a smoother while leaving captured_at at
    its 0.0 default collapses every interval to the 1/30 s fallback and
    silently degrades the adaptive cutoff — always feed the frame's real
    capture time when smoothing.

    apply_world_position (experimental) converts the payload's camera-space
    translation into a Blender-space armature offset, relative to
    translation_origin (typically the first frame's translation) so the
    character moves from where it stands instead of jumping to camera
    coordinates. Monocular depth is noisy — this stays opt-in.

    camera_pitch_radians compensates a tilted capture camera (the port of the
    POC's Camera Pitch control): it is folded into the orientation fix, so it
    only takes effect when apply_orientation_fix is on. Positive = camera
    looking down, negative = looking up; 0.0 (default) is no compensation.
    """
    allowed = limb_filter.allowed_bones()
    previous: Mapping[str, FloatArray] = (
        previous_quaternions if previous_quaternions is not None else {}
    )
    rotations: list[BoneRotation] = []
    world_offset: FloatArray | None = None

    if allowed is None:
        orient = np.asarray(payload.global_orient, dtype=np.float64)
        if apply_orientation_fix:
            orient = flip_global_orient(orient, camera_pitch_radians)
        rotations.append(_bone_rotation(PELVIS, orient, previous, smoother, captured_at))
        if apply_world_position:
            world_offset = _world_offset(payload.transl, translation_origin)

    for index, name in enumerate(BODY_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(
                _bone_rotation(name, payload.body_pose[index], previous, smoother, captured_at)
            )

    for index, name in enumerate(LEFT_HAND_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(
                _bone_rotation(name, payload.left_hand_pose[index], previous, smoother, captured_at)
            )

    for index, name in enumerate(RIGHT_HAND_JOINT_NAMES):
        if allowed is None or name in allowed:
            rotations.append(
                _bone_rotation(
                    name, payload.right_hand_pose[index], previous, smoother, captured_at
                )
            )

    return PoseApplication(
        clear_bones=allowed, rotations=tuple(rotations), world_offset=world_offset
    )


def _world_offset(transl: list[float], translation_origin: FloatArray | None) -> FloatArray:
    """Camera space (x right, y down, z forward) -> Blender space (x, z, -y)."""
    camera = np.asarray(transl, dtype=np.float64)
    if translation_origin is not None:
        camera = camera - np.asarray(translation_origin, dtype=np.float64)
    offset = np.asarray([camera[0], camera[2], -camera[1]], dtype=np.float64)
    offset.setflags(write=False)
    return offset


def _bone_rotation(
    name: str,
    axis_angle: FloatArray | list[float],
    previous: Mapping[str, FloatArray],
    smoother: PoseSmoother | None,
    captured_at: float,
) -> BoneRotation:
    quaternion = axis_angle_to_quaternion(np.asarray(axis_angle, dtype=np.float64))
    if smoother is not None:
        quaternion = np.asarray(smoother.smooth(name, quaternion, captured_at))
    reference = previous.get(name)
    if reference is not None:
        quaternion = make_sign_compatible(quaternion, reference)
    quaternion = quaternion.copy()
    quaternion.setflags(write=False)
    return BoneRotation(bone_name=name, quaternion=quaternion)
