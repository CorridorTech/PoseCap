"""Blender-side conversion of a humanoid armature to the PoseCap convention.

Implements doc/workflows.md § "Target armature requirements" for armatures
that don't follow it: (1) optionally re-rest the arms to a T-pose, (2)
rename mapped bones to SMPL-X joint names (vertex groups follow), (3)
reorient mapped bones to a fixed world frame (bone axis +Z, local z toward -Y,
pulled back through the object's rotation so a Y-up or Z-up import both land
right) so pose-bone local axes equal the SMPL-X joint frame, then (4) self-verify
with synthetic left_shoulder raise/swing probes. Assumes the armature's object
transform is a pure rotation with uniform, non-mirrored scale (checked).

The pure retarget domain (skeleton presets, family detection, mapping tables,
validation, probe expectations) lives in ``posecap_core.retarget`` and the
quaternion math in ``posecap_core.rotation``; this module re-exports those and
holds only the ``bpy`` orchestration. The re-export keeps the module a single
import surface for the dev CLI in tools/convert_target_armature.py, which loads
it by file path inside ``blender --background`` — that CLI puts the workspace
``core/src`` and ``contracts/src`` on ``sys.path`` first so ``posecap_core``
resolves without the extension installed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from posecap_core import (
    ARM_TARGETS,
    SMPLX_BODY_JOINTS,
    UE_MAPPING,
    PoseCapError,
    SkeletonPreset,
    axis_angle_to_quaternion,
    detect_skeleton_preset,
    mixamo_preset,
    probe_expectations,
    ue_preset,
    validate_mapping,
)

# Public surface: the re-exported retarget domain plus this module's bpy
# conversion API. Listed so the facade re-exports read as intentional.
__all__ = [
    "ARM_TARGETS",
    "SMPLX_BODY_JOINTS",
    "UE_MAPPING",
    "ConversionError",
    "ConversionResult",
    "SkeletonPreset",
    "convert_armature",
    "detect_skeleton_preset",
    "mixamo_preset",
    "probe_expectations",
    "ue_preset",
    "validate_mapping",
]


class ConversionError(PoseCapError):
    """A conversion failure with a user-facing message (GUIDELINES §2.2)."""


@dataclass(frozen=True)
class ConversionResult:
    """Self-verification outcome of a conversion."""

    probe_lines: tuple[str, ...]
    max_probe_error: float


def convert_armature(
    bpy,
    arm_obj,
    preset: SkeletonPreset,
    *,
    re_rest_t_pose: bool | None = None,
    bone_length: float = 10.0,
    probe_tolerance: float = 0.05,
) -> ConversionResult:  # pragma: no cover - exercised inside Blender only
    """Convert one armature in the open file; raises ConversionError on failure."""
    missing_joints = validate_mapping(preset.mapping)
    if missing_joints:
        raise ConversionError(f"mapping is missing SMPL-X joints: {', '.join(missing_joints)}")
    mesh_objs = _resolve_meshes(bpy, arm_obj, preset.mapping)
    # The reorient reads the object's rotation to place bones in a fixed world
    # frame; a mirrored (negative-scale) object transform has no pure-rotation
    # quaternion, so fail loudly with a fix instead of silently mis-orienting.
    if arm_obj.matrix_world.is_negative:
        raise ConversionError(
            "the armature has a mirrored (negative) scale — apply "
            "Object > Apply > Rotation & Scale, then convert again"
        )
    needs_re_rest = not preset.already_t_pose if re_rest_t_pose is None else re_rest_t_pose
    if needs_re_rest:
        _re_rest_tpose(bpy, arm_obj, mesh_objs, preset.arm_chains)
    _rename_and_reorient(bpy, arm_obj, mesh_objs, preset.mapping, bone_length)
    return _verify(bpy, arm_obj, probe_tolerance)


def _resolve_meshes(bpy, arm_obj, mapping):  # pragma: no cover - Blender only
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        raise ConversionError("pick an armature object first")
    mesh_objs = [
        o
        for o in bpy.data.objects
        if o.type == "MESH"
        and any(m.type == "ARMATURE" and m.object is arm_obj for m in o.modifiers)
    ]
    if not mesh_objs:
        raise ConversionError("no mesh is bound to this armature")
    absent = [bone for bone in mapping.values() if bone not in arm_obj.pose.bones]
    if absent:
        raise ConversionError(f"the armature is missing expected bones: {', '.join(absent)}")
    return mesh_objs


def _re_rest_tpose(bpy, arm_obj, mesh_objs, arm_chains):  # pragma: no cover - Blender only
    from mathutils import Matrix, Vector  # type: ignore  # Blender-bundled module

    def align(name, reference_child, target):
        bpy.context.view_layer.update()
        pose_bone = arm_obj.pose.bones[name]
        world = arm_obj.matrix_world
        head_world = world @ pose_bone.head
        tip = (
            world @ arm_obj.pose.bones[reference_child].head
            if reference_child
            else world @ pose_bone.tail
        )
        direction = (tip - head_world).normalized()
        rotation = direction.rotation_difference(Vector(target)).to_matrix().to_4x4()
        pivot = Matrix.Translation(head_world)
        pose_bone.matrix = world.inverted() @ (
            pivot @ rotation @ pivot.inverted() @ (world @ pose_bone.matrix)
        )

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    for side, target in ARM_TARGETS.items():
        for bone, child in arm_chains[side]:
            if bone in arm_obj.pose.bones:
                align(bone, child if child in arm_obj.pose.bones else None, target)
    bpy.ops.object.mode_set(mode="OBJECT")
    for mesh_obj in mesh_objs:
        bpy.context.view_layer.objects.active = mesh_obj
        modifier = next(m for m in mesh_obj.modifiers if m.type == "ARMATURE")
        bpy.ops.object.modifier_apply(modifier=modifier.name)
        rebind = mesh_obj.modifiers.new("Armature", "ARMATURE")
        rebind.object = arm_obj
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def _rename_and_reorient(bpy, arm_obj, mesh_objs, mapping, bone_length):
    # pragma: no cover - Blender only
    from mathutils import Vector  # type: ignore  # Blender-bundled module

    for smpl_name, source_name in mapping.items():
        arm_obj.data.bones[source_name].name = smpl_name
    for mesh_obj in mesh_objs:
        for smpl_name, source_name in mapping.items():
            group = mesh_obj.vertex_groups.get(source_name)
            if group is not None:
                group.name = smpl_name

    # Reorient to a fixed WORLD frame (+Z bone axis, local z toward -Y), not a
    # fixed armature-local one. Edit-bone geometry is armature-local, so the
    # target directions are pulled back through the object's rotation: a Z-up
    # import (UE, object rotation identity) is unchanged, while a Y-up import
    # (Mixamo, object rotation +90 deg X) gets the matching local tilt instead
    # of a frame that is 90 deg off (task 0008 Mixamo validation).
    inverse_object_rotation = arm_obj.matrix_world.to_quaternion().inverted()
    tail_direction = inverse_object_rotation @ Vector((0.0, 0.0, 1.0))
    roll_direction = inverse_object_rotation @ Vector((0.0, -1.0, 0.0))

    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    # Detach every bone's head from its parent's tail first. Mixamo (and other
    # FBX) skeletons import connected, so retargeting a bone's tail would drag
    # its child's head off the joint and collapse the anatomy into the reorient
    # axis; UE armatures import disconnected and were unaffected.
    for edit_bone in arm_obj.data.edit_bones:
        edit_bone.use_connect = False
    for smpl_name in mapping:
        edit_bone = arm_obj.data.edit_bones[smpl_name]
        head = edit_bone.head.copy()
        edit_bone.tail = head + tail_direction * bone_length
        edit_bone.align_roll(roll_direction)
    bpy.ops.object.mode_set(mode="OBJECT")


def _verify(bpy, arm_obj, relative_tolerance):  # pragma: no cover - Blender only
    def elbow_world():
        bpy.context.view_layer.update()
        return (arm_obj.matrix_world @ arm_obj.pose.bones["left_elbow"].head).copy()

    def apply_shoulder(axis_angle):
        for pose_bone in arm_obj.pose.bones:
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        before = elbow_world()
        quaternion = tuple(axis_angle_to_quaternion(axis_angle))
        arm_obj.pose.bones["left_shoulder"].rotation_quaternion = quaternion
        return elbow_world() - before

    scale = arm_obj.matrix_world.to_scale()[0]
    shoulder = arm_obj.pose.bones["left_shoulder"].head
    elbow = arm_obj.pose.bones["left_elbow"].head
    arm_length = (elbow - shoulder).length * scale
    tolerance = max(relative_tolerance * arm_length, 1e-4)
    expected = probe_expectations(arm_length)
    probes = (("raise_z", (0.0, 0.0, math.pi / 2)), ("swing_y", (0.0, math.pi / 2, 0.0)))
    lines: list[str] = []
    max_error = 0.0
    for label, axis_angle in probes:
        delta = apply_shoulder(axis_angle)
        want = expected[label]
        error = max(abs(delta[i] - want[i]) for i in range(3))
        max_error = max(max_error, error)
        lines.append(
            f"probe {label}: delta=({delta.x:+.3f},{delta.y:+.3f},{delta.z:+.3f}) "
            f"expected=({want[0]:+.3f},{want[1]:+.3f},{want[2]:+.3f}) err={error:.4f}"
        )
        if error > tolerance:
            raise ConversionError(
                f"probe {label} failed: error {error:.4f} > tolerance {tolerance:.4f}"
            )
    for pose_bone in arm_obj.pose.bones:
        pose_bone.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    return ConversionResult(probe_lines=tuple(lines), max_probe_error=max_error)
