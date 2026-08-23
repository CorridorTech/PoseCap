"""Headless Blender fixture for non-destructive rest-delta pose binding.

This file intentionally uses only synthetic two-bone armatures. It must never
load, write, or depend on SMPL-X model assets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

REPO_ROOT = Path(__file__).parents[3]
sys.path[:0] = [
    str(REPO_ROOT / "contracts" / "src"),
    str(REPO_ROOT / "core" / "src"),
    str(REPO_ROOT / "addon"),
]

RESULT_PATH = Path(__file__).parents[1] / "eval" / "result.json"
BONE_NAMES = ("pelvis", "spine")
EPSILON = 1e-5


def make_armature(name: str, *, target_rest: bool) -> bpy.types.Object:
    bpy.ops.object.armature_add(enter_editmode=True)
    armature = bpy.context.object
    assert armature is not None
    armature.name = name
    armature.data.name = f"{name}_data"

    edit_bones = armature.data.edit_bones
    edit_bones.remove(edit_bones[0])

    pelvis = edit_bones.new("pelvis")
    pelvis.head = Vector((0.0, 0.0, 0.0))
    if target_rest:
        pelvis.tail = Vector((0.0, 0.0, 1.0))
        pelvis.roll = 0.4
    else:
        pelvis.tail = Vector((0.0, 1.0, 0.0))
        pelvis.roll = -0.25

    spine = edit_bones.new("spine")
    spine.parent = pelvis
    spine.use_connect = True
    spine.head = pelvis.tail
    if target_rest:
        spine.tail = Vector((0.45, 0.25, 1.95))
        spine.roll = -0.3
    else:
        spine.tail = Vector((0.35, 1.9, 0.25))
        spine.roll = 0.2

    bpy.ops.object.mode_set(mode="POSE")
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature


def update() -> None:
    bpy.context.view_layer.update()


def rotation_error(actual: Matrix, expected: Matrix) -> float:
    return max(
        abs(actual[row][column] - expected[row][column]) for row in range(3) for column in range(3)
    )


def translation_error(actual: Matrix, expected: Matrix) -> float:
    return max(abs(actual[row][3] - expected[row][3]) for row in range(3))


def quaternion_error(actual, expected) -> float:
    return 1.0 - abs(actual.normalized().dot(expected.normalized()))


def apply_rest_delta(
    source: bpy.types.Object,
    target: bpy.types.Object,
    bone_name: str,
) -> Matrix:
    source_pose_bone = source.pose.bones[bone_name]
    target_pose_bone = target.pose.bones[bone_name]
    expected_pose_matrix = (
        source_pose_bone.matrix
        @ source_pose_bone.bone.matrix_local.inverted()
        @ target_pose_bone.bone.matrix_local
    )
    target_local_matrix = target.convert_space(
        pose_bone=target_pose_bone,
        matrix=expected_pose_matrix,
        from_space="POSE",
        to_space="LOCAL",
    )
    target_pose_bone.rotation_quaternion = target_local_matrix.to_quaternion()
    target_pose_bone.location = target_local_matrix.to_translation()
    target_pose_bone.scale = target_local_matrix.to_scale()
    return expected_pose_matrix


def target_child_rotation_for_parent_rotation(parent_rotation: Euler):
    source = make_armature("source_variant", target_rest=False)
    target = make_armature("target_variant", target_rest=True)
    source.pose.bones["pelvis"].rotation_quaternion = parent_rotation.to_quaternion()
    source.pose.bones["spine"].rotation_quaternion = Euler((-0.3, 0.4, 0.15)).to_quaternion()
    update()
    for bone_name in BONE_NAMES:
        apply_rest_delta(source, target, bone_name)
        update()
    return target.pose.bones["spine"].rotation_quaternion.copy()


def canonical_source_rest_orientation():
    """Measure the exact rest orientation made by the legacy converter recipe."""
    bpy.ops.object.armature_add(enter_editmode=True)
    armature = bpy.context.object
    assert armature is not None
    edit_bone = armature.data.edit_bones[0]
    edit_bone.head = Vector((0.0, 0.0, 0.0))
    edit_bone.tail = Vector((0.0, 0.0, 1.0))
    edit_bone.align_roll(Vector((0.0, -1.0, 0.0)))
    bpy.ops.object.mode_set(mode="OBJECT")
    return armature.data.bones[0].matrix_local.to_quaternion()


def verify_binding_builder() -> None:
    from posecap_addon.character_setup import (
        SMPLX_BODY_JOINTS,
        SkeletonPreset,
        build_pose_binding,
    )

    bpy.ops.object.armature_add(enter_editmode=True)
    armature = bpy.context.object
    assert armature is not None
    edit_bones = armature.data.edit_bones
    edit_bones.remove(edit_bones[0])
    for index, name in enumerate(SMPLX_BODY_JOINTS):
        bone = edit_bones.new(name)
        bone.head = Vector((float(index), 0.0, 0.0))
        bone.tail = Vector((float(index), 1.0, 0.0))
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.rotation_euler = Euler((0.2, -0.1, 0.3))
    before = {bone.name: bone.matrix_local.copy() for bone in armature.data.bones}
    preset = SkeletonPreset(
        "synthetic",
        "Synthetic",
        {name: name for name in SMPLX_BODY_JOINTS},
        {},
        True,
    )
    binding = build_pose_binding(armature, preset)
    if set(binding.bones) != set(SMPLX_BODY_JOINTS):
        raise AssertionError("binding did not retain every mapped source joint")
    if any(
        bone.name not in before or bone.matrix_local != before[bone.name]
        for bone in armature.data.bones
    ):
        raise AssertionError("binding builder mutated the armature rest data")


def main() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    source = make_armature("source", target_rest=False)
    target_local = make_armature("target_local", target_rest=True)
    target_matrix = make_armature("target_matrix", target_rest=True)
    target_naive = make_armature("target_naive", target_rest=True)

    source.pose.bones["pelvis"].rotation_quaternion = Euler((0.35, -0.2, 0.45)).to_quaternion()
    source.pose.bones["spine"].rotation_quaternion = Euler((-0.3, 0.4, 0.15)).to_quaternion()
    update()

    expected = {}
    for bone_name in BONE_NAMES:
        expected[bone_name] = apply_rest_delta(source, target_local, bone_name)
        update()

    for bone_name in BONE_NAMES:
        source_pose_bone = source.pose.bones[bone_name]
        target_pose_bone = target_matrix.pose.bones[bone_name]
        expected_matrix = (
            source_pose_bone.matrix
            @ source_pose_bone.bone.matrix_local.inverted()
            @ target_pose_bone.bone.matrix_local
        )
        target_pose_bone.matrix = expected_matrix
        update()

    for bone_name in BONE_NAMES:
        target_naive.pose.bones[bone_name].rotation_quaternion = source.pose.bones[
            bone_name
        ].rotation_quaternion.copy()
    update()

    local_component_rotation_errors = {
        bone_name: rotation_error(target_local.pose.bones[bone_name].matrix, expected[bone_name])
        for bone_name in BONE_NAMES
    }
    local_component_translation_errors = {
        bone_name: translation_error(target_local.pose.bones[bone_name].matrix, expected[bone_name])
        for bone_name in BONE_NAMES
    }
    matrix_rotation_errors = {
        bone_name: rotation_error(target_matrix.pose.bones[bone_name].matrix, expected[bone_name])
        for bone_name in BONE_NAMES
    }
    matrix_translation_errors = {
        bone_name: translation_error(
            target_matrix.pose.bones[bone_name].matrix, expected[bone_name]
        )
        for bone_name in BONE_NAMES
    }
    naive_rotation_errors = {
        bone_name: rotation_error(target_naive.pose.bones[bone_name].matrix, expected[bone_name])
        for bone_name in BONE_NAMES
    }
    if max(matrix_rotation_errors.values()) > EPSILON:
        raise AssertionError(f"Rest-delta matrix rotation diverged: {matrix_rotation_errors}")
    if min(naive_rotation_errors.values()) <= EPSILON:
        raise AssertionError(f"Fixture did not distinguish naive copying: {naive_rotation_errors}")

    compensation_rotation_errors = {}
    for bone_name in BONE_NAMES:
        source_pose_bone = source.pose.bones[bone_name]
        target_pose_bone = target_local.pose.bones[bone_name]
        compensation = (
            target_pose_bone.bone.matrix_local.to_quaternion().inverted()
            @ source_pose_bone.bone.matrix_local.to_quaternion()
        )
        mapped_rotation = (
            compensation @ source_pose_bone.rotation_quaternion @ compensation.inverted()
        )
        compensation_rotation_errors[bone_name] = quaternion_error(
            target_pose_bone.rotation_quaternion,
            mapped_rotation,
        )
    if max(compensation_rotation_errors.values()) > EPSILON:
        raise AssertionError(
            f"Rest compensation quaternion diverged: {compensation_rotation_errors}"
        )

    first_child_rotation = target_child_rotation_for_parent_rotation(Euler((0.35, -0.2, 0.45)))
    second_child_rotation = target_child_rotation_for_parent_rotation(Euler((-0.1, 0.25, -0.5)))
    parent_variance = 1.0 - abs(first_child_rotation.dot(second_child_rotation))
    if parent_variance > EPSILON:
        raise AssertionError(
            f"Mapped child rotation changed when only the parent changed: {parent_variance}"
        )

    canonical_source_rest = canonical_source_rest_orientation()
    verify_binding_builder()

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(
            {
                "blender_version": bpy.app.version_string,
                "epsilon": EPSILON,
                "local_component_rotation_errors": local_component_rotation_errors,
                "local_component_translation_errors": local_component_translation_errors,
                "matrix_rotation_errors": matrix_rotation_errors,
                "matrix_translation_errors": matrix_translation_errors,
                "naive_rotation_errors": naive_rotation_errors,
                "compensation_rotation_errors": compensation_rotation_errors,
                "child_rotation_parent_variance": parent_variance,
                "canonical_source_rest_orientation": tuple(canonical_source_rest),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "local_component_rotation_errors": local_component_rotation_errors,
                "local_component_translation_errors": local_component_translation_errors,
                "matrix_rotation_errors": matrix_rotation_errors,
                "matrix_translation_errors": matrix_translation_errors,
                "naive_rotation_errors": naive_rotation_errors,
            }
        )
    )


if __name__ == "__main__":
    main()
