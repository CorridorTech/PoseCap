import numpy as np
import pytest
from posecap_core import LandmarkPoseConverter


def test_neutral_landmarks_convert_to_neutral_body_pose() -> None:
    converter = LandmarkPoseConverter()

    pose = converter.convert(_neutral_landmarks())

    assert np.allclose(pose.global_orient, [0.0, 0.0, 0.0], atol=1e-7)
    assert np.allclose(pose.body_pose, np.zeros((21, 3)), atol=1e-7)


def test_forward_left_arm_becomes_shoulder_rotation() -> None:
    landmarks = _neutral_landmarks()
    landmarks["left_elbow"] = (0.4, 1.0, 0.3)
    landmarks["left_wrist"] = (0.4, 1.0, 0.6)

    pose = LandmarkPoseConverter().convert(landmarks)

    left_shoulder = pose.body_pose[15]
    assert left_shoulder == pytest.approx([0.0, -np.pi / 2.0, 0.0])


def _neutral_landmarks() -> dict[str, tuple[float, float, float]]:
    return {
        "left_hip": (0.2, 0.0, 0.0),
        "right_hip": (-0.2, 0.0, 0.0),
        "left_shoulder": (0.4, 1.0, 0.0),
        "right_shoulder": (-0.4, 1.0, 0.0),
        "left_elbow": (0.7, 1.0, 0.0),
        "right_elbow": (-0.7, 1.0, 0.0),
        "left_wrist": (1.0, 1.0, 0.0),
        "right_wrist": (-1.0, 1.0, 0.0),
        "left_knee": (0.2, -1.0, 0.0),
        "right_knee": (-0.2, -1.0, 0.0),
        "left_ankle": (0.2, -2.0, 0.0),
        "right_ankle": (-0.2, -2.0, 0.0),
        "left_heel": (0.2, -2.0, -0.1),
        "right_heel": (-0.2, -2.0, -0.1),
        "left_foot_index": (0.2, -2.0, 0.3),
        "right_foot_index": (-0.2, -2.0, 0.3),
        "left_ear": (0.1, 1.55, 0.0),
        "right_ear": (-0.1, 1.55, 0.0),
        "mouth_left": (0.04, 1.4, 0.0),
        "mouth_right": (-0.04, 1.4, 0.0),
        "nose": (0.0, 1.5, 0.0),
    }
