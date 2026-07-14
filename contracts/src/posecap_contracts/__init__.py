"""Wire formats shared by every PoseCap process. Stdlib only — by contract."""

from .backend_manifest import (
    BACKEND_MANIFEST_SCHEMA_VERSION,
    BackendCompatibility,
    PoseBackendManifest,
    decode_pose_backend_manifest,
)
from .codec import decode_pose_frame, encode_pose_frame
from .errors import (
    BackendManifestDecodeError,
    ContractError,
    FrameDecodeError,
    JobStatusDecodeError,
)
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
from .model_assets import (
    MPI_DOWNLOAD_URL,
    REQUIRED_MODEL_ASSETS,
    ModelAsset,
    MpiDownload,
    PublicDownload,
)

__all__ = [
    "BACKEND_MANIFEST_SCHEMA_VERSION",
    "MPI_DOWNLOAD_URL",
    "NUM_BETAS",
    "NUM_BODY_JOINTS",
    "NUM_EXPRESSION",
    "NUM_HAND_JOINTS",
    "REQUIRED_MODEL_ASSETS",
    "SCHEMA_VERSION",
    "BackendCompatibility",
    "BackendManifestDecodeError",
    "ContractError",
    "FrameDecodeError",
    "FrameStatus",
    "JobState",
    "JobStatus",
    "JobStatusDecodeError",
    "ModelAsset",
    "MpiDownload",
    "PoseBackendManifest",
    "PoseFrame",
    "PosePayload",
    "PublicDownload",
    "Vec3",
    "decode_job_status",
    "decode_pose_backend_manifest",
    "decode_pose_frame",
    "encode_job_status",
    "encode_pose_frame",
]
