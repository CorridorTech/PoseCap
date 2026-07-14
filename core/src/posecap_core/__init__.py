"""PoseCap domain logic. Imports stdlib, numpy, and contracts only — by contract."""

from .application import (
    KEYFRAME_DATA_PATH,
    BoneRotation,
    PoseApplication,
    plan_pose_application,
)
from .errors import PoseCapError
from .filters import LimbFilter
from .landmark_pose import LandmarkMap, LandmarkPoseConverter
from .orientation import flip_global_orient
from .ports import PoseStream
from .retarget import (
    ARM_TARGETS,
    SMPLX_BODY_JOINTS,
    UE_MAPPING,
    SkeletonPreset,
    detect_skeleton_preset,
    mixamo_mapping,
    mixamo_preset,
    probe_expectations,
    ue_preset,
    validate_mapping,
)
from .rotation import (
    IDENTITY_QUATERNION,
    axis_angle_to_quaternion,
    make_sign_compatible,
    quaternion_multiply,
    quaternion_to_axis_angle,
)
from .skeleton import (
    BODY_JOINT_NAMES,
    LEFT_HAND_JOINT_NAMES,
    PELVIS,
    RIGHT_HAND_JOINT_NAMES,
    SMPLX_JOINT_NAMES,
)
from .smoothing import PoseSmoother

__all__ = [
    "ARM_TARGETS",
    "BODY_JOINT_NAMES",
    "IDENTITY_QUATERNION",
    "KEYFRAME_DATA_PATH",
    "LEFT_HAND_JOINT_NAMES",
    "PELVIS",
    "RIGHT_HAND_JOINT_NAMES",
    "SMPLX_BODY_JOINTS",
    "SMPLX_JOINT_NAMES",
    "UE_MAPPING",
    "BoneRotation",
    "PoseCapError",
    "LimbFilter",
    "LandmarkMap",
    "LandmarkPoseConverter",
    "PoseApplication",
    "PoseSmoother",
    "PoseStream",
    "SkeletonPreset",
    "axis_angle_to_quaternion",
    "detect_skeleton_preset",
    "flip_global_orient",
    "make_sign_compatible",
    "mixamo_mapping",
    "mixamo_preset",
    "plan_pose_application",
    "probe_expectations",
    "quaternion_multiply",
    "quaternion_to_axis_angle",
    "ue_preset",
    "validate_mapping",
]
