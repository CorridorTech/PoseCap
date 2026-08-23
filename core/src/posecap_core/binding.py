"""Pure mapping from SMPL-X pose instructions to an untouched target rig.

The binding is calculated during setup by a Blender-facing adapter.  On the
live path this module only rewrites an immutable :class:`PoseApplication`, so
it neither knows about nor mutates Blender data.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .application import BoneRotation, PoseApplication
from .errors import PoseCapError
from .rotation import ZERO_ANGLE, FloatArray, quaternion_multiply


@dataclass(frozen=True)
class BoundBone:
    """One SMPL-X joint mapped to an original bone on the target rig.

    ``compensation_quaternion`` changes from the SMPL-X local basis into the
    target bone's local basis.  ``neutral_quaternion`` is the target pose that
    represents a neutral capture, which lets reset honour an untouched rig's
    current rest pose rather than assuming a global identity.
    """

    target_bone_name: str
    compensation_quaternion: FloatArray
    neutral_quaternion: FloatArray

    def __post_init__(self) -> None:
        if not self.target_bone_name:
            raise PoseCapError("bound target bone name cannot be empty")
        object.__setattr__(
            self,
            "compensation_quaternion",
            _normalized_readonly(self.compensation_quaternion),
        )
        object.__setattr__(
            self,
            "neutral_quaternion",
            _normalized_readonly(self.neutral_quaternion),
        )


@dataclass(frozen=True)
class PoseBinding:
    """Immutable lookup from SMPL-X joint names to original target bones."""

    bones: Mapping[str, BoundBone]

    def __post_init__(self) -> None:
        copied = dict(self.bones)
        if any(not name for name in copied):
            raise PoseCapError("SMPL-X joint name cannot be empty")
        targets = [bone.target_bone_name for bone in copied.values()]
        if len(targets) != len(set(targets)):
            raise PoseCapError("each target bone can be bound only once")
        object.__setattr__(self, "bones", MappingProxyType(copied))

    def source_previous_quaternions(
        self,
        target_previous_quaternions: Mapping[str, FloatArray],
    ) -> dict[str, FloatArray]:
        """Express target-writer history back in SMPL-X joint coordinates."""
        previous: dict[str, FloatArray] = {}
        for source_name, bone in self.bones.items():
            target_quaternion = target_previous_quaternions.get(bone.target_bone_name)
            if target_quaternion is not None:
                previous[source_name] = _source_quaternion(target_quaternion, bone)
        return previous


def compensation_from_rest_orientations(
    source_rest_orientation: FloatArray,
    target_rest_orientation: FloatArray,
) -> FloatArray:
    """Build a target-basis compensation from accumulated rest orientations.

    Both inputs must describe the same global reference frame. The Blender
    adapter therefore supplies each bone's accumulated rest orientation and
    includes any armature-object rotation before calling this function. The
    resulting quaternion maps a streamed source rotation through
    ``compensation @ source @ compensation^-1``.
    """
    source = _normalized_readonly(source_rest_orientation)
    target = _normalized_readonly(target_rest_orientation)
    return _normalized_readonly(quaternion_multiply(_conjugate(target), source))


def apply_binding(plan: PoseApplication, binding: PoseBinding) -> PoseApplication:
    """Rewrite a SMPL-X pose plan to the target rig's original bone names.

    Unmapped joints are intentionally omitted.  This permits a body-only
    binding to stream while reporting missing optional fingers during setup.
    """
    clear_bones = _bound_clear_bones(plan.clear_bones, binding)
    neutral_rotations = tuple(
        BoneRotation(
            bone_name=bone.target_bone_name,
            quaternion=bone.neutral_quaternion,
        )
        for bone in _bound_bones_for_clear(plan.clear_bones, binding)
    )
    rotations = tuple(
        _bound_rotation(rotation, binding.bones[rotation.bone_name])
        for rotation in plan.rotations
        if rotation.bone_name in binding.bones
    )
    return PoseApplication(
        clear_bones=clear_bones,
        rotations=rotations,
        world_offset=plan.world_offset,
        neutral_rotations=neutral_rotations,
    )


def _bound_clear_bones(
    source_clear_bones: frozenset[str] | None,
    binding: PoseBinding,
) -> frozenset[str]:
    return frozenset(
        bone.target_bone_name for bone in _bound_bones_for_clear(source_clear_bones, binding)
    )


def _bound_bones_for_clear(
    source_clear_bones: frozenset[str] | None,
    binding: PoseBinding,
) -> tuple[BoundBone, ...]:
    source_names = binding.bones if source_clear_bones is None else source_clear_bones
    return tuple(
        binding.bones[source_name] for source_name in source_names if source_name in binding.bones
    )


def _bound_rotation(rotation: BoneRotation, bone: BoundBone) -> BoneRotation:
    compensated = quaternion_multiply(
        bone.compensation_quaternion,
        quaternion_multiply(rotation.quaternion, _conjugate(bone.compensation_quaternion)),
    )
    quaternion = quaternion_multiply(bone.neutral_quaternion, compensated)
    quaternion = _normalized_readonly(quaternion)
    return BoneRotation(bone_name=bone.target_bone_name, quaternion=quaternion)


def _source_quaternion(target_quaternion: FloatArray, bone: BoundBone) -> FloatArray:
    without_neutral = quaternion_multiply(
        _conjugate(bone.neutral_quaternion),
        target_quaternion,
    )
    return quaternion_multiply(
        _conjugate(bone.compensation_quaternion),
        quaternion_multiply(without_neutral, bone.compensation_quaternion),
    )


def _conjugate(quaternion: FloatArray) -> FloatArray:
    result = np.asarray(quaternion, dtype=np.float64).copy()
    result[1:] *= -1.0
    return result


def _normalized_readonly(quaternion: FloatArray) -> FloatArray:
    result = np.asarray(quaternion, dtype=np.float64)
    if result.shape != (4,):
        raise PoseCapError("quaternion must have four components")
    norm = float(np.linalg.norm(result))
    if norm < ZERO_ANGLE:
        raise PoseCapError("quaternion cannot have zero norm")
    normalized = (result / norm).copy()
    normalized.setflags(write=False)
    return normalized
