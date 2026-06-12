"""Pose-frame types shared by every PoseCap process.

All rotations are axis-angle (Rodrigues) vectors in radians. Array order is
the SMPL-X joint order: index, not name, is the contract — body joint i maps
to skeleton position i+1 (position 0 is the pelvis, driven by global_orient).
"""

from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = 1
NUM_BODY_JOINTS = 21
NUM_HAND_JOINTS = 15
NUM_BETAS = 10
NUM_EXPRESSION = 10

FrameStatus = Literal["ok", "no_person"]

Vec3 = list[float]


@dataclass(frozen=True)
class PosePayload:
    """SMPL-X parameters for one frame; lengths are enforced on decode."""

    global_orient: Vec3
    body_pose: list[Vec3]
    left_hand_pose: list[Vec3]
    right_hand_pose: list[Vec3]
    jaw_pose: Vec3
    betas: list[float]
    expression: list[float]
    transl: Vec3


@dataclass(frozen=True)
class PoseFrame:
    """One streamed frame; `pose` is present exactly when `status` is "ok".

    `captured_at` is the producer's wall-clock timestamp in epoch seconds,
    stamped at frame capture — the latency metric compares it against the
    consumer's apply time.
    """

    schema_version: int
    seq: int
    captured_at: float
    status: FrameStatus
    pose: PosePayload | None
