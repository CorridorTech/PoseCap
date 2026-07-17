"""Retarget domain: skeleton presets, bone-name mapping, and probe expectations.

Pure logic (stdlib only) that maps a humanoid character skeleton onto the
SMPL-X joint convention. The Blender-side orchestration that applies this to a
live armature lives in the addon (``character_setup.py``); this module holds
the family tables, family detection, mapping validation, and the geometric
probe expectations the converter self-verifies against.

Presets ship for the Unreal Engine humanoid skeleton (validated on two
Fortnite exports) and the Mixamo skeleton (Adobe's free character library;
grounded on the mixamorig <-> SMPL correspondence used across retarget tools).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .skeleton import LEFT_HAND_JOINT_NAMES, RIGHT_HAND_JOINT_NAMES

SMPLX_BODY_JOINTS = (
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
)

# Unreal Engine humanoid skeleton (Fortnite exports use it verbatim).
UE_MAPPING: dict[str, str] = {
    "pelvis": "pelvis",
    "left_hip": "thigh_l",
    "right_hip": "thigh_r",
    "spine1": "spine_01",
    "left_knee": "calf_l",
    "right_knee": "calf_r",
    "spine2": "spine_03",
    "left_ankle": "foot_l",
    "right_ankle": "foot_r",
    "spine3": "spine_05",
    "left_foot": "ball_l",
    "right_foot": "ball_r",
    "neck": "neck_01",
    "left_collar": "clavicle_l",
    "right_collar": "clavicle_r",
    "head": "head",
    "left_shoulder": "upperarm_l",
    "right_shoulder": "upperarm_r",
    "left_elbow": "lowerarm_l",
    "right_elbow": "lowerarm_r",
    "left_wrist": "hand_l",
    "right_wrist": "hand_r",
}

# Mixamo skeleton suffixes (index-aligned with the SMPL joint order; the
# export prefix varies — "mixamorig:", "mixamorig5:", or none at all).
_MIXAMO_SUFFIXES: dict[str, str] = {
    "pelvis": "Hips",
    "left_hip": "LeftUpLeg",
    "right_hip": "RightUpLeg",
    "spine1": "Spine",
    "left_knee": "LeftLeg",
    "right_knee": "RightLeg",
    "spine2": "Spine1",
    "left_ankle": "LeftFoot",
    "right_ankle": "RightFoot",
    "spine3": "Spine2",
    "left_foot": "LeftToeBase",
    "right_foot": "RightToeBase",
    "neck": "Neck",
    "left_collar": "LeftShoulder",
    "right_collar": "RightShoulder",
    "head": "Head",
    "left_shoulder": "LeftArm",
    "right_shoulder": "RightArm",
    "left_elbow": "LeftForeArm",
    "right_elbow": "RightForeArm",
    "left_wrist": "LeftHand",
    "right_wrist": "RightHand",
}


def _mixamo_hand_suffix(joint: str) -> str:
    side, finger_joint = joint.split("_", maxsplit=1)
    return f"{side.title()}Hand{finger_joint[:-1].title()}{finger_joint[-1]}"


_MIXAMO_HAND_SUFFIXES: dict[str, str] = {
    joint: _mixamo_hand_suffix(joint) for joint in LEFT_HAND_JOINT_NAMES + RIGHT_HAND_JOINT_NAMES
}

_MIXAMO_PREFIX_PATTERN = re.compile(r"^(mixamorig\d*[:_])Hips$")

# Arm chains re-rested to a T-pose: (bone, reference child whose HEAD gives
# the limb direction — UE exports orient bone tails off-limb, so tails lie).
_UE_ARM_CHAINS = {
    "l": (
        ("upperarm_l", "lowerarm_l"),
        ("lowerarm_l", "hand_l"),
        ("hand_l", "middle_metacarpal_l"),
    ),
    "r": (
        ("upperarm_r", "lowerarm_r"),
        ("lowerarm_r", "hand_r"),
        ("hand_r", "middle_metacarpal_r"),
    ),
}
ARM_TARGETS = {"l": (1.0, 0.0, 0.0), "r": (-1.0, 0.0, 0.0)}

# Relative tolerance of the converter's self-verification probes, as a
# fraction of the measured arm length. Shared by the Blender-side converter
# default and the re-rest trigger margin below.
PROBE_RELATIVE_TOLERANCE = 0.05

# A preset's already_t_pose is a claim about the download default, not the
# character in front of us: Mixamo auto-rigged custom uploads keep whatever
# bind pose the mesh was uploaded in (task 0033). Arms measured further than
# this from their T-pose target need the re-rest regardless of the claim.
# PROBE_RELATIVE_TOLERANCE fails a small-angle droop from ~2.9 degrees
# (degrees(0.05)), so the trigger fires with margin below that.
T_POSE_MAX_ARM_DEVIATION_DEGREES = 2.0

ArmLines = dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]


def needs_t_pose_re_rest(preset: SkeletonPreset, arm_lines: ArmLines) -> bool:
    """Whether the measured arms invalidate a preset's T-pose claim.

    ``arm_lines`` maps ``ARM_TARGETS`` keys to (shoulder_head, elbow_head)
    world positions in any unit. A preset that never claims a T-pose always
    re-rests; a claimed T-pose re-rests when either arm measures further
    than ``T_POSE_MAX_ARM_DEVIATION_DEGREES`` from its target.
    """
    if not preset.already_t_pose:
        return True
    return any(
        arm_t_pose_deviation_degrees(shoulder, elbow, side) > T_POSE_MAX_ARM_DEVIATION_DEGREES
        for side, (shoulder, elbow) in arm_lines.items()
    )


def arm_t_pose_deviation_degrees(
    shoulder_head: tuple[float, float, float],
    elbow_head: tuple[float, float, float],
    side: str,
) -> float:
    """Angle in degrees between the shoulder-to-elbow world line and the T-pose target.

    ``side`` is an ``ARM_TARGETS`` key (``"l"`` or ``"r"``); positions are
    world-space coordinates in any unit (only the direction matters).
    """
    direction = tuple(
        elbow - shoulder for elbow, shoulder in zip(elbow_head, shoulder_head, strict=True)
    )
    length = math.sqrt(sum(component * component for component in direction))
    if length == 0.0:
        return 180.0
    target = ARM_TARGETS[side]
    cosine = sum(d * t for d, t in zip(direction, target, strict=True)) / length
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


ArmChains = dict[str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class SkeletonPreset:
    """One convertible skeleton family."""

    name: str
    label: str
    mapping: dict[str, str]
    arm_chains: ArmChains
    already_t_pose: bool


def ue_preset() -> SkeletonPreset:
    """The Unreal Engine / Fortnite skeleton preset; A-pose rest, so re-rest applies."""
    return SkeletonPreset(
        name="ue",
        label="Unreal Engine / Fortnite",
        mapping=dict(UE_MAPPING),
        arm_chains=_UE_ARM_CHAINS,
        already_t_pose=False,
    )


def mixamo_mapping(prefix: str) -> dict[str, str]:
    """The Mixamo bone mapping for one export prefix ('' when stripped)."""
    return {joint: prefix + suffix for joint, suffix in _MIXAMO_SUFFIXES.items()}


def mixamo_preset(prefix: str, *, include_hands: bool = False) -> SkeletonPreset:
    """The Mixamo skeleton preset for one export prefix ('' when stripped)."""
    # Library characters download in T-pose, so the re-rest defaults to off —
    # but the claim is geometry-verified at conversion time because custom
    # auto-rigged uploads keep the uploaded bind pose (task 0033).
    chains: ArmChains = {
        "l": (
            (prefix + "LeftArm", prefix + "LeftForeArm"),
            (prefix + "LeftForeArm", prefix + "LeftHand"),
            (prefix + "LeftHand", prefix + "LeftHandMiddle1"),
        ),
        "r": (
            (prefix + "RightArm", prefix + "RightForeArm"),
            (prefix + "RightForeArm", prefix + "RightHand"),
            (prefix + "RightHand", prefix + "RightHandMiddle1"),
        ),
    }
    mapping = mixamo_mapping(prefix)
    if include_hands:
        mapping.update(_mixamo_hand_mapping(prefix))
    return SkeletonPreset(
        name="mixamo",
        label="Mixamo",
        mapping=mapping,
        arm_chains=chains,
        already_t_pose=True,
    )


def detect_skeleton_preset(bone_names: set[str] | frozenset[str]) -> SkeletonPreset | None:
    """Sniff the skeleton family from bone names (None when unrecognized)."""
    names = set(bone_names)
    if {"thigh_l", "clavicle_l"} <= names:
        return ue_preset()
    for name in names:
        match = _MIXAMO_PREFIX_PATTERN.match(name)
        if match and match.group(1) + "LeftUpLeg" in names:
            prefix = match.group(1)
            return mixamo_preset(prefix, include_hands=_has_complete_mixamo_hands(prefix, names))
    if {"Hips", "LeftUpLeg", "LeftForeArm"} <= names:
        return mixamo_preset("", include_hands=_has_complete_mixamo_hands("", names))
    return None


def _mixamo_hand_mapping(prefix: str) -> dict[str, str]:
    return {joint: prefix + suffix for joint, suffix in _MIXAMO_HAND_SUFFIXES.items()}


def _has_complete_mixamo_hands(prefix: str, bone_names: set[str]) -> bool:
    return set(_mixamo_hand_mapping(prefix).values()).issubset(bone_names)


def validate_mapping(mapping: dict[str, str]) -> list[str]:
    """Return the SMPL-X joints missing from a mapping (empty = valid)."""
    return [name for name in SMPLX_BODY_JOINTS if name not in mapping]


def probe_expectations(arm_length: float) -> dict[str, tuple[float, float, float]]:
    """Expected world elbow displacement per probe on a correct armature.

    raise_z (+z 90 deg): the T-pose arm (along +X) swings up — the elbow rises
    by the shoulder-to-elbow length and pulls inward by the same amount.
    swing_y (+y 90 deg): the arm swings behind the body (+Y world).
    """
    return {
        "raise_z": (-arm_length, 0.0, arm_length),
        "swing_y": (-arm_length, arm_length, 0.0),
    }
