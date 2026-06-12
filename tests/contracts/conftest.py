import pytest
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    SCHEMA_VERSION,
    PoseFrame,
    PosePayload,
)


def _build_ok_frame() -> PoseFrame:
    """A deterministic, fully-populated frame; also the golden-fixture source."""
    body_pose = [[0.0, 0.0, 0.0] for _ in range(NUM_BODY_JOINTS)]
    body_pose[0] = [0.5, 0.0, 0.0]
    payload = PosePayload(
        global_orient=[0.1, 0.2, 0.3],
        body_pose=body_pose,
        left_hand_pose=[[0.0, 0.0, 0.0] for _ in range(NUM_HAND_JOINTS)],
        right_hand_pose=[[0.0, 0.25, 0.0] for _ in range(NUM_HAND_JOINTS)],
        jaw_pose=[0.0, 0.0, 0.0],
        betas=[0.5] * NUM_BETAS,
        expression=[0.0] * NUM_EXPRESSION,
        transl=[0.0, 1.0, 2.5],
    )
    return PoseFrame(
        schema_version=SCHEMA_VERSION,
        seq=42,
        captured_at=1780900000.25,
        status="ok",
        pose=payload,
    )


def _build_no_person_frame() -> PoseFrame:
    return PoseFrame(
        schema_version=SCHEMA_VERSION,
        seq=43,
        captured_at=1780900000.5,
        status="no_person",
        pose=None,
    )


@pytest.fixture
def ok_frame() -> PoseFrame:
    return _build_ok_frame()


@pytest.fixture
def no_person_frame() -> PoseFrame:
    return _build_no_person_frame()
