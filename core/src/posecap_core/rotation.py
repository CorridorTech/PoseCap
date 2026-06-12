"""Axis-angle / quaternion math on numpy arrays.

Quaternions are (w, x, y, z), unit length. Axis-angle (Rodrigues) vectors
carry the rotation axis scaled by the angle in radians — the wire format's
rotation representation (contracts).
"""

import math

import numpy as np
from numpy.typing import NDArray

from .errors import PoseCapError

FloatArray = NDArray[np.float64]

ZERO_ANGLE = 1e-12
"""Magnitudes below this are treated as no rotation (radians)."""

IDENTITY_QUATERNION: FloatArray = np.array([1.0, 0.0, 0.0, 0.0])
IDENTITY_QUATERNION.setflags(write=False)


def axis_angle_to_quaternion(axis_angle: FloatArray) -> FloatArray:
    """Convert a Rodrigues vector to a unit quaternion; zero vector maps to identity."""
    vector = np.asarray(axis_angle, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    if angle < ZERO_ANGLE:
        return IDENTITY_QUATERNION.copy()
    axis = vector / angle
    half = angle / 2.0
    sine = math.sin(half)
    return np.array([math.cos(half), axis[0] * sine, axis[1] * sine, axis[2] * sine])


def quaternion_to_axis_angle(quaternion: FloatArray) -> FloatArray:
    """Convert a quaternion to a Rodrigues vector; identity (either sign) maps to zeros.

    Raises PoseCapError on a zero-norm input — that is a corrupt
    quaternion, not a rotation, and must not silently become NaN on the
    per-frame hot path.
    """
    q = np.asarray(quaternion, dtype=np.float64)
    norm = float(np.linalg.norm(q))
    if norm < ZERO_ANGLE:
        raise PoseCapError("zero-norm quaternion cannot be converted to axis-angle")
    q = q / norm
    if q[0] < 0.0:
        # Canonical short-way representation: q and -q encode the same
        # rotation; picking w >= 0 keeps the angle within [0, pi]. (The POC's
        # mathutils path emitted the long-way form here — same rotation,
        # bigger numbers — and nothing downstream observes the difference.)
        q = -q
    w = float(np.clip(q[0], -1.0, 1.0))
    sine = math.sqrt(max(0.0, 1.0 - w * w))
    if sine < ZERO_ANGLE:
        return np.zeros(3)
    angle = 2.0 * math.acos(w)
    return (q[1:] / sine) * angle


def quaternion_multiply(a: FloatArray, b: FloatArray) -> FloatArray:
    """Hamilton product a ⊗ b — apply rotation b first, then a."""
    aw, ax, ay, az = np.asarray(a, dtype=np.float64)
    bw, bx, by, bz = np.asarray(b, dtype=np.float64)
    return np.array(
        [
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        ]
    )


def make_sign_compatible(quaternion: FloatArray, reference: FloatArray) -> FloatArray:
    """Return quaternion or its negation, whichever is nearer the reference.

    q and -q encode the same rotation; picking the hemisphere of the previous
    frame's quaternion prevents 360-degree pops between consecutive live
    frames and broken keyframe interpolation (port of the POC's load-bearing
    mathutils make_compatible call).
    """
    q = np.asarray(quaternion, dtype=np.float64)
    if float(np.dot(q, np.asarray(reference, dtype=np.float64))) < 0.0:
        return -q
    return q
