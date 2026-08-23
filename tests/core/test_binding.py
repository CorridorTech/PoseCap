"""Behavior tests for non-destructive pose-binding maps."""

import numpy as np
import pytest
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    PosePayload,
)
from posecap_core import (
    BoneRotation,
    BoundBone,
    LimbFilter,
    PoseApplication,
    PoseBinding,
    apply_binding,
    axis_angle_to_quaternion,
    compensation_from_rest_orientations,
    plan_pose_application,
)


def test_binding_rewrites_a_rotation_to_the_original_target_bone_name() -> None:
    source_quaternion = np.asarray([0.0, 0.0, 0.0, 1.0])
    plan = PoseApplication(
        clear_bones=frozenset({"left_shoulder"}),
        rotations=(BoneRotation("left_shoulder", source_quaternion),),
    )
    binding = PoseBinding(
        {
            "left_shoulder": BoundBone(
                target_bone_name="mixamorig:LeftArm",
                compensation_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
                neutral_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
            )
        }
    )

    bound = apply_binding(plan, binding)

    assert bound.clear_bones == frozenset({"mixamorig:LeftArm"})
    assert [rotation.bone_name for rotation in bound.rotations] == ["mixamorig:LeftArm"]
    assert np.array_equal(bound.rotations[0].quaternion, source_quaternion)


def test_plan_writes_only_bound_original_bones_without_mutating_the_rig() -> None:
    payload = PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[0.0, 0.0, 0.0]] * NUM_BODY_JOINTS,
        left_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        right_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 0.0, 0.0],
    )
    binding = PoseBinding(
        {
            "left_hip": BoundBone(
                target_bone_name="mixamorig:LeftUpLeg",
                compensation_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
                neutral_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
            )
        }
    )

    plan = plan_pose_application(payload, LimbFilter(), binding=binding)

    assert plan.clear_bones == frozenset({"mixamorig:LeftUpLeg"})
    assert [rotation.bone_name for rotation in plan.rotations] == ["mixamorig:LeftUpLeg"]


def test_binding_applies_basis_compensation_and_a_target_neutral_pose() -> None:
    source = axis_angle_to_quaternion(np.asarray([np.pi / 2.0, 0.0, 0.0]))
    plan = PoseApplication(
        clear_bones=frozenset({"left_shoulder"}),
        rotations=(BoneRotation("left_shoulder", source),),
    )
    binding = PoseBinding(
        {
            "left_shoulder": BoundBone(
                target_bone_name="mixamorig:LeftArm",
                compensation_quaternion=axis_angle_to_quaternion(
                    np.asarray([0.0, 0.0, np.pi / 2.0])
                ),
                neutral_quaternion=axis_angle_to_quaternion(np.asarray([0.0, np.pi / 2.0, 0.0])),
            )
        }
    )

    bound = apply_binding(plan, binding)

    # Z-basis compensation rotates the incoming X axis to Y, then the target
    # neutral rotation is applied in target-local space.
    expected = axis_angle_to_quaternion(np.asarray([0.0, np.pi, 0.0]))
    assert np.allclose(bound.rotations[0].quaternion, expected)
    assert not bound.rotations[0].quaternion.flags.writeable
    assert [rotation.bone_name for rotation in bound.neutral_rotations] == ["mixamorig:LeftArm"]
    assert np.allclose(
        bound.neutral_rotations[0].quaternion,
        axis_angle_to_quaternion(np.asarray([0.0, np.pi / 2.0, 0.0])),
    )


def test_compensation_is_target_rest_inverse_then_source_rest() -> None:
    source_rest = axis_angle_to_quaternion(np.asarray([0.0, 0.0, np.pi / 2.0]))
    target_rest = axis_angle_to_quaternion(np.asarray([np.pi / 2.0, 0.0, 0.0]))

    compensation = compensation_from_rest_orientations(source_rest, target_rest)

    assert np.allclose(compensation, [0.5, -0.5, 0.5, 0.5])
    assert not compensation.flags.writeable


def test_binding_uses_target_named_previous_rotations_for_sign_continuity() -> None:
    payload = PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[np.pi / 2.0, 0.0, 0.0]] + [[0.0, 0.0, 0.0]] * (NUM_BODY_JOINTS - 1),
        left_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        right_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 0.0, 0.0],
    )
    binding = PoseBinding(
        {
            "left_hip": BoundBone(
                target_bone_name="mixamorig:LeftUpLeg",
                compensation_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
                neutral_quaternion=np.asarray([1.0, 0.0, 0.0, 0.0]),
            )
        }
    )
    first = plan_pose_application(payload, LimbFilter(), binding=binding)
    previous = {first.rotations[0].bone_name: -first.rotations[0].quaternion}

    second = plan_pose_application(
        payload,
        LimbFilter(),
        previous_quaternions=previous,
        binding=binding,
    )

    assert float(np.dot(second.rotations[0].quaternion, previous["mixamorig:LeftUpLeg"])) > 0.0


def test_binding_preserves_limb_filtering_when_rewriting_target_names() -> None:
    payload = PosePayload(
        global_orient=[0.0, 0.0, 0.0],
        body_pose=[[0.0, 0.0, 0.0]] * NUM_BODY_JOINTS,
        left_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        right_hand_pose=[[0.0, 0.0, 0.0]] * NUM_HAND_JOINTS,
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 0.0, 0.0],
    )
    identity = np.asarray([1.0, 0.0, 0.0, 0.0])
    binding = PoseBinding(
        {
            "left_hip": BoundBone("mixamorig:LeftUpLeg", identity, identity),
            "left_shoulder": BoundBone("mixamorig:LeftArm", identity, identity),
        }
    )

    plan = plan_pose_application(payload, LimbFilter(legs_left=True), binding=binding)

    assert plan.clear_bones == frozenset({"mixamorig:LeftUpLeg"})
    assert [rotation.bone_name for rotation in plan.rotations] == ["mixamorig:LeftUpLeg"]


def test_binding_defensively_keeps_compensation_values_immutable() -> None:
    compensation = np.asarray([1.0, 0.0, 0.0, 0.0])
    bone = BoundBone("mixamorig:LeftArm", compensation, compensation)

    compensation[0] = 0.0

    assert np.array_equal(bone.compensation_quaternion, [1.0, 0.0, 0.0, 0.0])
    with pytest.raises(ValueError, match="read-only"):
        bone.compensation_quaternion[0] = 0.0
