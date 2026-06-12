import math

import numpy as np
import pytest
from posecap_core import (
    IDENTITY_QUATERNION,
    PoseCapError,
    axis_angle_to_quaternion,
    make_sign_compatible,
    quaternion_multiply,
    quaternion_to_axis_angle,
)

CASES = [
    [0.5, 0.0, 0.0],
    [0.0, -1.2, 0.0],
    [0.0, 0.0, 3.0],
    [0.7, -0.3, 1.1],
    [-2.0, 2.0, -0.5],
    [1e-6, 0.0, 0.0],
]


def test_zero_vector_maps_to_identity() -> None:
    assert np.allclose(axis_angle_to_quaternion(np.zeros(3)), IDENTITY_QUATERNION)


def test_identity_maps_to_zero_vector() -> None:
    assert np.allclose(quaternion_to_axis_angle(IDENTITY_QUATERNION), np.zeros(3))
    assert np.allclose(quaternion_to_axis_angle(-IDENTITY_QUATERNION), np.zeros(3))


def test_round_trip_preserves_rotation() -> None:
    # Angles stay below pi: the quaternion double-cover folds larger angles
    # onto their short-way equivalents, which is correct but not identity.
    for case in CASES:
        recovered = quaternion_to_axis_angle(axis_angle_to_quaternion(np.array(case)))
        assert np.allclose(recovered, case, atol=1e-9), case


def test_zero_norm_quaternion_raises_typed_error() -> None:
    with pytest.raises(PoseCapError, match="zero-norm"):
        quaternion_to_axis_angle(np.zeros(4))


def test_exported_identity_is_immutable() -> None:
    with pytest.raises(ValueError, match="read-only"):
        IDENTITY_QUATERNION[0] = 0.0


def test_quaternions_are_unit_length() -> None:
    for case in CASES:
        quaternion = axis_angle_to_quaternion(np.array(case))
        assert math.isclose(float(np.linalg.norm(quaternion)), 1.0, abs_tol=1e-12)


def test_known_quarter_turn_about_x() -> None:
    quaternion = axis_angle_to_quaternion(np.array([math.pi / 2, 0.0, 0.0]))
    expected = np.array([math.cos(math.pi / 4), math.sin(math.pi / 4), 0.0, 0.0])
    assert np.allclose(quaternion, expected)


def test_multiply_composes_rotations() -> None:
    quarter_x = axis_angle_to_quaternion(np.array([math.pi / 2, 0.0, 0.0]))
    composed = quaternion_multiply(quarter_x, quarter_x)
    assert np.allclose(quaternion_to_axis_angle(composed), [math.pi, 0.0, 0.0], atol=1e-9)


def test_multiply_identity_is_neutral() -> None:
    quaternion = axis_angle_to_quaternion(np.array([0.7, -0.3, 1.1]))
    assert np.allclose(quaternion_multiply(IDENTITY_QUATERNION, quaternion), quaternion)
    assert np.allclose(quaternion_multiply(quaternion, IDENTITY_QUATERNION), quaternion)


def test_sign_compatible_negates_opposed_quaternion() -> None:
    quaternion = axis_angle_to_quaternion(np.array([0.5, 0.0, 0.0]))
    assert np.allclose(make_sign_compatible(-quaternion, quaternion), quaternion)
    assert np.allclose(make_sign_compatible(quaternion, quaternion), quaternion)


def test_sign_continuity_across_the_flip_boundary() -> None:
    """Sweeping a rotation past 180 degrees must not pop quaternion signs.

    Without sign matching, the angles on either side of pi produce
    quaternions in opposite hemispheres; interpolating between them spins
    the long way round — the live-stream artifact this function prevents.
    """
    angles = np.linspace(math.radians(150), math.radians(210), 13)
    previous = axis_angle_to_quaternion(np.array([angles[0], 0.0, 0.0]))
    for angle in angles[1:]:
        current = make_sign_compatible(
            axis_angle_to_quaternion(np.array([angle, 0.0, 0.0])), previous
        )
        assert float(np.dot(current, previous)) > 0.0, math.degrees(angle)
        previous = current
