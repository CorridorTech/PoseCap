"""Wire formats shared by every PoseCap process. Stdlib only — by contract."""

from .codec import decode_pose_frame, encode_pose_frame
from .errors import ContractError, FrameDecodeError, JobStatusDecodeError
from .frames import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    FrameStatus,
    PoseFrame,
    PosePayload,
    Vec3,
)
from .job import JobState, JobStatus, decode_job_status, encode_job_status

__all__ = [
    "NUM_BETAS",
    "NUM_BODY_JOINTS",
    "NUM_EXPRESSION",
    "NUM_HAND_JOINTS",
    "SCHEMA_VERSION",
    "ContractError",
    "FrameDecodeError",
    "FrameStatus",
    "JobState",
    "JobStatus",
    "JobStatusDecodeError",
    "PoseFrame",
    "PosePayload",
    "Vec3",
    "decode_job_status",
    "decode_pose_frame",
    "encode_job_status",
    "encode_pose_frame",
]
