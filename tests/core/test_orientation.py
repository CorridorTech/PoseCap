import math

import numpy as np
from posecap_core import flip_global_orient


def _rotation_matrix(axis_angle: np.ndarray) -> np.ndarray:
    """Independent Rodrigues-formula implementation for cross-checking."""
    angle = float(np.linalg.norm(axis_angle))
    if angle < 1e-12:
        return np.eye(3)
    axis = axis_angle / angle
    k = np.array(
        [
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ]
    )
    return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)


def test_zero_rotation_is_unchanged() -> None:
    assert np.allclose(flip_global_orient(np.zeros(3)), np.zeros(3))


def test_subthreshold_input_passes_through_unchanged() -> None:
    """Inputs below ZERO_ANGLE take the zero-rotation branch — no flip applied."""
    result = flip_global_orient(np.array([1e-13, 0.0, 0.0]))
    assert np.allclose(result, [1e-13, 0.0, 0.0])


def test_golden_pair_pins_the_flip() -> None:
    """Hard-coded input/output pair (task 0002 AC).

    Expected value derived once from the independent Rodrigues-matrix
    composition of the same operation the POC performs with mathutils
    (fix_quat @ quat, fix on the left) and frozen here as a literal.
    """
    result = flip_global_orient(np.array([0.7, -0.3, 1.1]))
    expected = [-2.0573346685941796, 1.3372188622805132, 0.3646960533492306]
    assert np.allclose(result, expected, atol=1e-12)


def test_x_180_input_cancels_to_identity() -> None:
    result = flip_global_orient(np.array([math.pi, 0.0, 0.0]))
    assert np.allclose(result, np.zeros(3), atol=1e-9)


def test_matches_independent_matrix_composition() -> None:
    flip = np.array([math.pi, 0.0, 0.0])
    for case in ([0.7, -0.3, 1.1], [0.0, 1.5, 0.0], [-0.2, 0.4, -2.1]):
        case_array = np.array(case)
        expected = _rotation_matrix(flip) @ _rotation_matrix(case_array)
        actual = _rotation_matrix(flip_global_orient(case_array))
        assert np.allclose(actual, expected, atol=1e-9), case


def test_camera_pitch_zero_matches_plain_flip() -> None:
    """camera_pitch=0 is exactly the 180-degree flip — no regression."""
    case = np.array([0.7, -0.3, 1.1])
    assert np.allclose(flip_global_orient(case, camera_pitch_radians=0.0), flip_global_orient(case))


def test_camera_pitch_adds_x_rotation() -> None:
    """A non-zero camera pitch composes an extra X rotation onto the flip.

    The flip and the camera pitch share the camera X axis, so the total is
    R_x(pi + camera_pitch) — a port of the POC's Camera Pitch control that
    compensates a tilted camera (positive = looking down, negative = up)."""
    pitch = math.radians(-45.0)
    flip_plus_pitch = np.array([math.pi + pitch, 0.0, 0.0])
    for case in ([0.7, -0.3, 1.1], [0.0, 1.5, 0.0], [-0.2, 0.4, -2.1]):
        case_array = np.array(case)
        expected = _rotation_matrix(flip_plus_pitch) @ _rotation_matrix(case_array)
        actual = _rotation_matrix(flip_global_orient(case_array, camera_pitch_radians=pitch))
        assert np.allclose(actual, expected, atol=1e-9), case


def test_camera_pitch_ignored_for_zero_orient() -> None:
    """A zero global_orient stays unchanged even with a camera pitch set —
    flipping an already-upright pelvis would invert it."""
    result = flip_global_orient(np.zeros(3), camera_pitch_radians=math.radians(-45.0))
    assert np.allclose(result, np.zeros(3))
