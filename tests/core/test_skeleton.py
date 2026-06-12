from posecap_contracts import NUM_BODY_JOINTS, NUM_HAND_JOINTS
from posecap_core import (
    BODY_JOINT_NAMES,
    LEFT_HAND_JOINT_NAMES,
    PELVIS,
    RIGHT_HAND_JOINT_NAMES,
    SMPLX_JOINT_NAMES,
)


def test_joint_count_is_smplx_55() -> None:
    assert len(SMPLX_JOINT_NAMES) == 55


def test_pelvis_is_position_zero() -> None:
    assert SMPLX_JOINT_NAMES[0] == PELVIS


def test_body_block_matches_wire_contract() -> None:
    assert len(BODY_JOINT_NAMES) == NUM_BODY_JOINTS
    assert BODY_JOINT_NAMES[0] == "left_hip"
    assert BODY_JOINT_NAMES[-1] == "right_wrist"


def test_hand_blocks_are_trailing_left_then_right() -> None:
    assert len(LEFT_HAND_JOINT_NAMES) == NUM_HAND_JOINTS
    assert len(RIGHT_HAND_JOINT_NAMES) == NUM_HAND_JOINTS
    assert LEFT_HAND_JOINT_NAMES[0] == "left_index1"
    assert RIGHT_HAND_JOINT_NAMES[0] == "right_index1"
    assert SMPLX_JOINT_NAMES[-1] == "right_thumb3"


def test_every_index_maps_to_exactly_one_name() -> None:
    assert len(set(SMPLX_JOINT_NAMES)) == len(SMPLX_JOINT_NAMES)
