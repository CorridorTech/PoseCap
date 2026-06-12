"""PEAR camera-frame orientation fix.

PEAR's global orientation is expressed in the camera frame and arrives
upside-down for Blender's world; the fix pre-multiplies a 180-degree
rotation about X (port of the POC's smplx_import_flip_pear behavior).
"""

import math

import numpy as np

from .rotation import (
    ZERO_ANGLE,
    FloatArray,
    axis_angle_to_quaternion,
    quaternion_multiply,
    quaternion_to_axis_angle,
)

_FLIP_X_180: FloatArray = axis_angle_to_quaternion(np.array([math.pi, 0.0, 0.0]))
_FLIP_X_180.setflags(write=False)


def flip_global_orient(axis_angle: FloatArray) -> FloatArray:
    """Pre-multiply the global orientation by a 180-degree X rotation.

    A zero rotation is returned unchanged — the POC only applied the fix
    when the incoming angle was non-zero.
    """
    vector = np.asarray(axis_angle, dtype=np.float64)
    if float(np.linalg.norm(vector)) < ZERO_ANGLE:
        return vector.copy()
    rotated = quaternion_multiply(_FLIP_X_180, axis_angle_to_quaternion(vector))
    return quaternion_to_axis_angle(rotated)
