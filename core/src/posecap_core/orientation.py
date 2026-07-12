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


def flip_global_orient(axis_angle: FloatArray, camera_pitch_radians: float = 0.0) -> FloatArray:
    """Pre-multiply the global orientation by a rotation about the camera X axis.

    The base 180-degree flip ports the POC's smplx_import_flip_pear (PEAR's
    camera-frame orient arrives upside-down for Blender's world).

    camera_pitch_radians compensates a tilted camera — the port of the POC's
    dropped "Camera Pitch" control. The flip and the camera pitch share the
    camera X axis, so they combine into a single ``pi + camera_pitch`` rotation
    (positive = camera looking down, negative = looking up, POC convention).
    Default 0.0 reproduces the plain 180-degree flip exactly.

    A zero rotation is returned unchanged — the POC only applied the fix when
    the incoming angle was non-zero (flipping an already-upright pelvis would
    invert it), so a camera pitch never rotates a zero orientation either.
    """
    vector = np.asarray(axis_angle, dtype=np.float64)
    if float(np.linalg.norm(vector)) < ZERO_ANGLE:
        return vector.copy()
    if camera_pitch_radians == 0.0:
        flip = _FLIP_X_180
    else:
        flip = axis_angle_to_quaternion(np.array([math.pi + camera_pitch_radians, 0.0, 0.0]))
    rotated = quaternion_multiply(flip, axis_angle_to_quaternion(vector))
    return quaternion_to_axis_angle(rotated)
