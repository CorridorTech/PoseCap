"""Convert canonical 3D body landmarks into the PoseCap rotation contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeAlias

import numpy as np
from posecap_contracts import NUM_BETAS, NUM_EXPRESSION, NUM_HAND_JOINTS, PosePayload

from .rotation import quaternion_to_axis_angle
from .skeleton import BODY_JOINT_NAMES

LandmarkMap: TypeAlias = Mapping[str, Sequence[float]]

_EPSILON = 1e-8
_IDENTITY = np.eye(3, dtype=np.float64)

_PARENTS = {
    "left_hip": "pelvis",
    "right_hip": "pelvis",
    "spine1": "pelvis",
    "left_knee": "left_hip",
    "right_knee": "right_hip",
    "spine2": "spine1",
    "left_ankle": "left_knee",
    "right_ankle": "right_knee",
    "spine3": "spine2",
    "left_foot": "left_ankle",
    "right_foot": "right_ankle",
    "neck": "spine3",
    "left_collar": "spine3",
    "right_collar": "spine3",
    "head": "neck",
    "left_shoulder": "left_collar",
    "right_shoulder": "right_collar",
    "left_elbow": "left_shoulder",
    "right_elbow": "right_shoulder",
    "left_wrist": "left_elbow",
    "right_wrist": "right_elbow",
}


class LandmarkPoseConverter:
    """Stateful canonical-landmark to SMPL-X-order body rotation adapter.

    The input axes are PoseCap canonical axes: +X anatomical left, +Y up,
    +Z forward. Long-bone axial twist is resolved from the parent anatomical
    frame; it is an approximation because joint centres do not observe twist.
    """

    def convert(self, landmarks: LandmarkMap) -> PosePayload:
        """Convert one landmark map to a pelvis-locked SMPL-X pose payload (axis-angle, radians)."""
        points = {name: _point(landmarks, name) for name in _required_landmarks()}
        global_frames = _global_frames(points)
        body_pose = [
            _matrix_to_axis_angle(global_frames[_PARENTS[name]].T @ global_frames[name]).tolist()
            for name in BODY_JOINT_NAMES
        ]
        zero_hand = [[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)]
        return PosePayload(
            global_orient=_matrix_to_axis_angle(global_frames["pelvis"]).tolist(),
            body_pose=body_pose,
            left_hand_pose=[row.copy() for row in zero_hand],
            right_hand_pose=[row.copy() for row in zero_hand],
            jaw_pose=[0.0, 0.0, 0.0],
            betas=[0.0] * NUM_BETAS,
            expression=[0.0] * NUM_EXPRESSION,
            transl=[0.0, 0.0, 0.0],
        )


def _global_frames(points: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    hip_center = _midpoint(points["left_hip"], points["right_hip"])
    shoulder_center = _midpoint(points["left_shoulder"], points["right_shoulder"])
    pelvis = _frame_from_xy(points["left_hip"] - points["right_hip"], shoulder_center - hip_center)
    chest = _frame_from_xy(
        points["left_shoulder"] - points["right_shoulder"], shoulder_center - hip_center
    )
    head = _frame_from_xy(
        points["left_ear"] - points["right_ear"],
        points["nose"] - _midpoint(points["mouth_left"], points["mouth_right"]),
    )
    frames: dict[str, np.ndarray] = {
        "pelvis": pelvis,
        "spine1": pelvis,
        "spine2": pelvis,
        "spine3": chest,
        "neck": chest,
        "head": head,
        "left_collar": chest,
        "right_collar": chest,
    }
    for side in ("left", "right"):
        hip = points[f"{side}_hip"]
        knee = points[f"{side}_knee"]
        ankle = points[f"{side}_ankle"]
        foot_index = points[f"{side}_foot_index"]
        hip_frame = _frame_from_xy(pelvis[:, 0], hip - knee)
        knee_frame = _frame_from_xy(hip_frame[:, 0], knee - ankle)
        ankle_frame = _frame_from_xz(knee_frame[:, 0], foot_index - ankle)
        frames[f"{side}_hip"] = hip_frame
        frames[f"{side}_knee"] = knee_frame
        frames[f"{side}_ankle"] = ankle_frame
        frames[f"{side}_foot"] = ankle_frame

        shoulder = points[f"{side}_shoulder"]
        elbow = points[f"{side}_elbow"]
        wrist = points[f"{side}_wrist"]
        direction_sign = 1.0 if side == "left" else -1.0
        shoulder_frame = _frame_from_xy(direction_sign * (elbow - shoulder), chest[:, 1])
        elbow_frame = _frame_from_xy(direction_sign * (wrist - elbow), shoulder_frame[:, 1])
        frames[f"{side}_shoulder"] = shoulder_frame
        frames[f"{side}_elbow"] = elbow_frame
        frames[f"{side}_wrist"] = elbow_frame
    return frames


def _required_landmarks() -> tuple[str, ...]:
    return (
        "left_hip",
        "right_hip",
        "left_shoulder",
        "right_shoulder",
        "left_elbow",
        "right_elbow",
        "left_wrist",
        "right_wrist",
        "left_knee",
        "right_knee",
        "left_ankle",
        "right_ankle",
        "left_heel",
        "right_heel",
        "left_foot_index",
        "right_foot_index",
        "left_ear",
        "right_ear",
        "mouth_left",
        "mouth_right",
        "nose",
    )


def _point(landmarks: LandmarkMap, name: str) -> np.ndarray:
    try:
        point = np.asarray(landmarks[name], dtype=np.float64)
    except KeyError as error:
        raise ValueError(f"missing landmark: {name}") from error
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise ValueError(f"landmark {name} must contain three finite numbers")
    return point


def _midpoint(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return (a + b) * 0.5


def _frame_from_xy(x_hint: np.ndarray, y_hint: np.ndarray) -> np.ndarray:
    x = _unit(x_hint)
    y = _unit(y_hint - x * float(np.dot(x, y_hint)))
    z = _unit(np.cross(x, y))
    y = _unit(np.cross(z, x))
    return np.column_stack((x, y, z))


def _frame_from_xz(x_hint: np.ndarray, z_hint: np.ndarray) -> np.ndarray:
    x = _unit(x_hint)
    z = _unit(z_hint - x * float(np.dot(x, z_hint)))
    y = _unit(np.cross(z, x))
    z = _unit(np.cross(x, y))
    return np.column_stack((x, y, z))


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < _EPSILON:
        raise ValueError("landmarks do not define a stable anatomical frame")
    return vector / norm


def _matrix_to_axis_angle(matrix: np.ndarray) -> np.ndarray:
    m = np.asarray(matrix, dtype=np.float64)
    trace = float(np.trace(m))
    if trace > 0.0:
        scale = 2.0 * np.sqrt(trace + 1.0)
        quaternion = np.array(
            [
                0.25 * scale,
                (m[2, 1] - m[1, 2]) / scale,
                (m[0, 2] - m[2, 0]) / scale,
                (m[1, 0] - m[0, 1]) / scale,
            ]
        )
    else:
        index = int(np.argmax(np.diag(m)))
        j = (index + 1) % 3
        k = (index + 2) % 3
        scale = 2.0 * np.sqrt(max(_EPSILON, 1.0 + m[index, index] - m[j, j] - m[k, k]))
        quaternion = np.zeros(4)
        quaternion[index + 1] = 0.25 * scale
        quaternion[0] = (m[k, j] - m[j, k]) / scale
        quaternion[j + 1] = (m[j, index] + m[index, j]) / scale
        quaternion[k + 1] = (m[k, index] + m[index, k]) / scale
    return quaternion_to_axis_angle(quaternion)
