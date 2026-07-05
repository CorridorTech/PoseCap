from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    PosePayload,
)
from posecap_core import BODY_JOINT_NAMES, LimbFilter, flip_global_orient, plan_pose_application

LEFT_ARM_RAISE_BONE = "left_shoulder"
LEFT_ARM_RAISE_AXIS_ANGLE = [0.0, 0.0, math.pi / 2.0]
DIAGNOSTIC_BONES = ("pelvis", LEFT_ARM_RAISE_BONE, "right_shoulder", "left_elbow")
_ROUND_DIGITS = 12


def left_arm_raise_report() -> dict[str, Any]:
    """Return a JSON-serializable POC-parity report for a synthetic arm pose."""
    payload = _left_arm_raise_payload()
    posecap = {
        rotation.bone_name: rotation.quaternion
        for rotation in plan_pose_application(payload, LimbFilter()).rotations
    }
    poc = _poc_quaternion_map(payload)
    bone_reports = {
        bone_name: {
            "axis_angle": _axis_angle_for_bone(payload, bone_name),
            "posecap_quaternion": _rounded_quaternion(posecap[bone_name]),
            "poc_quaternion": _rounded_quaternion(poc[bone_name]),
            "matches_poc": _quaternion_close(posecap[bone_name], poc[bone_name]),
        }
        for bone_name in DIAGNOSTIC_BONES
    }
    return {
        "diagnostic_pose": "left_shoulder_positive_z",
        "interpretation": (
            "This pins PoseCap math to Dean's POC path. Visual arm direction still depends "
            "on the target armature rest pose and bone local axes."
        ),
        "matches_poc": all(_quaternion_close(posecap[name], poc[name]) for name in poc),
        "non_identity_bones": [
            name for name in posecap if not _quaternion_close(posecap[name], _identity_quaternion())
        ],
        "bone_reports": bone_reports,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Emit a PoseCap-vs-POC orientation diagnostic for a synthetic left arm pose."
    )
    parser.add_argument("--pretty", action="store_true", help="print indented JSON")
    args = parser.parse_args(argv)
    indent = 2 if args.pretty else None
    print(json.dumps(left_arm_raise_report(), indent=indent, sort_keys=True))
    return 0


def _left_arm_raise_payload() -> PosePayload:
    body_pose = [[0.0, 0.0, 0.0] for _ in range(NUM_BODY_JOINTS)]
    body_pose[BODY_JOINT_NAMES.index(LEFT_ARM_RAISE_BONE)] = LEFT_ARM_RAISE_AXIS_ANGLE
    return PosePayload(
        global_orient=[0.1, 0.2, 0.3],
        body_pose=body_pose,
        left_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        right_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 0.0, 0.0],
    )


def _poc_quaternion_map(payload: PosePayload) -> dict[str, np.ndarray]:
    """Port Dean's POC pose.py path: pelvis flip, then direct Rodrigues writes."""
    global_orient = flip_global_orient(np.asarray(payload.global_orient, dtype=np.float64))
    quaternions = {"pelvis": _poc_quaternion_from_rodrigues(global_orient)}
    for index, bone_name in enumerate(BODY_JOINT_NAMES):
        quaternions[bone_name] = _poc_quaternion_from_rodrigues(payload.body_pose[index])
    return quaternions


def _poc_quaternion_from_rodrigues(axis_angle: Sequence[float] | NDArray[np.float64]) -> np.ndarray:
    vector = np.asarray(axis_angle, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    if angle < 1e-12:
        return _identity_quaternion()
    axis = vector / angle
    half = angle / 2.0
    return np.asarray(
        [
            math.cos(half),
            float(axis[0]) * math.sin(half),
            float(axis[1]) * math.sin(half),
            float(axis[2]) * math.sin(half),
        ],
        dtype=np.float64,
    )


def _axis_angle_for_bone(payload: PosePayload, bone_name: str) -> list[float]:
    if bone_name == "pelvis":
        return payload.global_orient
    if bone_name in BODY_JOINT_NAMES:
        return payload.body_pose[BODY_JOINT_NAMES.index(bone_name)]
    return [0.0, 0.0, 0.0]


def _rounded_quaternion(quaternion: np.ndarray) -> list[float]:
    return [round(float(value), _ROUND_DIGITS) for value in quaternion]


def _quaternion_close(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.allclose(a, b, atol=1e-12))


def _identity_quaternion() -> np.ndarray:
    return np.asarray([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


if __name__ == "__main__":
    raise SystemExit(main())
