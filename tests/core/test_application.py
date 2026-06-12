import math

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
    KEYFRAME_DATA_PATH,
    LimbFilter,
    axis_angle_to_quaternion,
    plan_pose_application,
)


@pytest.fixture
def payload() -> PosePayload:
    return PosePayload(
        global_orient=[0.0, 0.0, 1.0],
        body_pose=[[0.1 * i, 0.0, 0.0] for i in range(NUM_BODY_JOINTS)],
        left_hand_pose=[[0.0, 0.05 * i, 0.0] for i in range(NUM_HAND_JOINTS)],
        right_hand_pose=[[0.0, 0.0, 0.05 * i] for i in range(NUM_HAND_JOINTS)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.0] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 0.0, 0.0],
    )


def test_unfiltered_plan_covers_pelvis_body_and_hands(payload: PosePayload) -> None:
    plan = plan_pose_application(payload, LimbFilter())
    assert plan.clear_bones is None
    assert len(plan.rotations) == 1 + NUM_BODY_JOINTS + 2 * NUM_HAND_JOINTS
    assert plan.rotations[0].bone_name == "pelvis"


def test_active_filter_limits_rotations_and_drops_pelvis(payload: PosePayload) -> None:
    plan = plan_pose_application(payload, LimbFilter(legs_left=True))
    names = {rotation.bone_name for rotation in plan.rotations}
    assert names == {"left_hip", "left_knee", "left_ankle", "left_foot"}
    assert plan.clear_bones == frozenset(names)


def test_orientation_fix_changes_pelvis_only(payload: PosePayload) -> None:
    fixed = plan_pose_application(payload, LimbFilter(), apply_orientation_fix=True)
    raw = plan_pose_application(payload, LimbFilter(), apply_orientation_fix=False)
    assert not np.allclose(fixed.rotations[0].quaternion, raw.rotations[0].quaternion)
    for fixed_rotation, raw_rotation in zip(fixed.rotations[1:], raw.rotations[1:], strict=True):
        assert np.allclose(fixed_rotation.quaternion, raw_rotation.quaternion)


def test_raw_pelvis_matches_wire_value(payload: PosePayload) -> None:
    plan = plan_pose_application(payload, LimbFilter(), apply_orientation_fix=False)
    expected = axis_angle_to_quaternion(np.array([0.0, 0.0, 1.0]))
    assert np.allclose(plan.rotations[0].quaternion, expected)


def test_previous_quaternions_enforce_sign_continuity(payload: PosePayload) -> None:
    near_pi = math.radians(179.0)
    past_pi = math.radians(181.0)
    first = plan_pose_application(
        PosePayload(
            global_orient=[0.0, 0.0, 0.0],
            body_pose=[[near_pi, 0.0, 0.0]] + [[0.0, 0.0, 0.0]] * (NUM_BODY_JOINTS - 1),
            left_hand_pose=payload.left_hand_pose,
            right_hand_pose=payload.right_hand_pose,
            jaw_pose=[0.0, 0.0, 0.0],
            betas=payload.betas,
            expression=payload.expression,
            transl=payload.transl,
        ),
        LimbFilter(),
    )
    previous = {rotation.bone_name: rotation.quaternion for rotation in first.rotations}
    second = plan_pose_application(
        PosePayload(
            global_orient=[0.0, 0.0, 0.0],
            body_pose=[[past_pi, 0.0, 0.0]] + [[0.0, 0.0, 0.0]] * (NUM_BODY_JOINTS - 1),
            left_hand_pose=payload.left_hand_pose,
            right_hand_pose=payload.right_hand_pose,
            jaw_pose=[0.0, 0.0, 0.0],
            betas=payload.betas,
            expression=payload.expression,
            transl=payload.transl,
        ),
        LimbFilter(),
        previous_quaternions=previous,
    )
    left_hip_first = first.rotations[1].quaternion
    left_hip_second = second.rotations[1].quaternion
    assert float(np.dot(left_hip_first, left_hip_second)) > 0.0


def test_keyframe_data_path_is_rotation_quaternion() -> None:
    assert KEYFRAME_DATA_PATH == "rotation_quaternion"


def test_plan_quaternions_are_immutable(payload: PosePayload) -> None:
    """Plans double as the next frame's previous_quaternions — nothing may mutate them."""
    plan = plan_pose_application(payload, LimbFilter())
    with pytest.raises(ValueError, match="read-only"):
        plan.rotations[0].quaternion[0] = 0.0
