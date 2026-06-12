import pytest
from posecap_core import LimbFilter

LEFT_FINGER_COUNT = 15
ARM_LEFT = {"left_shoulder", "left_elbow", "left_wrist"}
LEGS_LEFT = {"left_hip", "left_knee", "left_ankle", "left_foot"}


def test_inactive_filter_allows_all_bones() -> None:
    assert LimbFilter().allowed_bones() is None
    assert LimbFilter().is_active() is False


@pytest.mark.parametrize(
    ("limb_filter", "must_contain", "size"),
    [
        (LimbFilter(fingers_left=True), {"left_index1", "left_thumb3"}, LEFT_FINGER_COUNT),
        (
            LimbFilter(hands_left=True),
            {"left_wrist", "left_index1"},
            LEFT_FINGER_COUNT + 1,
        ),
        (
            LimbFilter(arms_left=True),
            ARM_LEFT | {"left_index1"},
            LEFT_FINGER_COUNT + 3,
        ),
        (LimbFilter(legs_left=True), LEGS_LEFT, 4),
        (
            LimbFilter(arms_left=True, legs_right=True),
            ARM_LEFT | {"right_hip", "right_knee", "right_ankle", "right_foot"},
            LEFT_FINGER_COUNT + 3 + 4,
        ),
    ],
)
def test_filter_whitelists_match_poc_semantics(
    limb_filter: LimbFilter, must_contain: set[str], size: int
) -> None:
    allowed = limb_filter.allowed_bones()
    assert allowed is not None
    assert must_contain <= allowed
    assert len(allowed) == size


def test_right_side_mirrors_left() -> None:
    left = LimbFilter(arms_left=True).allowed_bones()
    right = LimbFilter(arms_right=True).allowed_bones()
    assert left is not None and right is not None
    assert {name.replace("left_", "right_") for name in left} == right


def test_active_filter_never_includes_pelvis() -> None:
    every_flag = LimbFilter(
        arms_left=True,
        arms_right=True,
        hands_left=True,
        hands_right=True,
        fingers_left=True,
        fingers_right=True,
        legs_left=True,
        legs_right=True,
    )
    allowed = every_flag.allowed_bones()
    assert allowed is not None
    assert "pelvis" not in allowed
