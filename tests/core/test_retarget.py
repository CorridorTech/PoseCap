"""Behavior tests for the retarget domain (task 0011).

Relocated from tests/addon/test_character_setup.py: the preset/mapping/
detection/validation logic is pure domain and now lives in posecap_core,
tested without Blender.
"""

import math

import numpy as np
import pytest
from posecap_core.retarget import (
    PROBE_RELATIVE_TOLERANCE,
    SMPLX_BODY_JOINTS,
    T_POSE_MAX_ARM_DEVIATION_DEGREES,
    UE_MAPPING,
    arm_t_pose_deviation_degrees,
    detect_skeleton_preset,
    mixamo_mapping,
    mixamo_preset,
    needs_t_pose_re_rest,
    probe_expectations,
    ue_preset,
    validate_mapping,
)
from posecap_core.rotation import axis_angle_to_quaternion


def test_ue_mapping_covers_all_smplx_body_joints() -> None:
    assert validate_mapping(UE_MAPPING) == []
    assert set(UE_MAPPING) == set(SMPLX_BODY_JOINTS)


def test_mixamo_mapping_covers_all_smplx_body_joints_with_the_prefix() -> None:
    mapping = mixamo_mapping("mixamorig:")
    assert validate_mapping(mapping) == []
    assert mapping["pelvis"] == "mixamorig:Hips"
    assert mapping["left_hip"] == "mixamorig:LeftUpLeg"
    assert mapping["spine1"] == "mixamorig:Spine"
    assert mapping["spine2"] == "mixamorig:Spine1"
    assert mapping["spine3"] == "mixamorig:Spine2"
    assert mapping["left_collar"] == "mixamorig:LeftShoulder"
    assert mapping["left_shoulder"] == "mixamorig:LeftArm"
    assert mapping["left_elbow"] == "mixamorig:LeftForeArm"
    assert mapping["left_wrist"] == "mixamorig:LeftHand"
    assert mapping["left_foot"] == "mixamorig:LeftToeBase"


def test_full_mixamo_auto_detection_maps_every_finger() -> None:
    prefix = "mixamorig:"
    source_bones = set(mixamo_mapping(prefix).values())
    source_bones.update(
        f"{prefix}{side}Hand{finger}{joint}"
        for side in ("Left", "Right")
        for finger in ("Index", "Middle", "Pinky", "Ring", "Thumb")
        for joint in range(1, 4)
    )

    preset = detect_skeleton_preset(source_bones)

    assert preset is not None
    assert {
        f"{side}_{finger}{joint}"
        for side in ("left", "right")
        for finger in ("index", "middle", "pinky", "ring", "thumb")
        for joint in range(1, 4)
    } <= set(preset.mapping)


def test_mixamo_with_an_incomplete_hand_stays_body_only() -> None:
    prefix = "mixamorig:"
    source_bones = set(mixamo_mapping(prefix).values())
    source_bones.add(f"{prefix}LeftHandIndex1")

    preset = detect_skeleton_preset(source_bones)

    assert preset is not None
    assert set(preset.mapping) == set(SMPLX_BODY_JOINTS)


def test_detects_the_unreal_skeleton_from_bone_names() -> None:
    bones = {"pelvis", "thigh_l", "thigh_r", "clavicle_l", "spine_05", "hand_r"}
    preset = detect_skeleton_preset(bones)
    assert preset is not None
    assert preset.name == "ue"
    assert preset.mapping == UE_MAPPING


def test_detects_mixamo_with_the_standard_prefix() -> None:
    bones = {"mixamorig:Hips", "mixamorig:LeftUpLeg", "mixamorig:LeftForeArm"}
    preset = detect_skeleton_preset(bones)
    assert preset is not None
    assert preset.name == "mixamo"
    assert preset.mapping["pelvis"] == "mixamorig:Hips"


def test_detects_mixamo_with_a_numbered_prefix() -> None:
    bones = {"mixamorig5:Hips", "mixamorig5:LeftUpLeg", "mixamorig5:LeftForeArm"}
    preset = detect_skeleton_preset(bones)
    assert preset is not None
    assert preset.name == "mixamo"
    assert preset.mapping["pelvis"] == "mixamorig5:Hips"


def test_detects_mixamo_exported_without_a_prefix() -> None:
    bones = {"Hips", "LeftUpLeg", "LeftForeArm", "Spine2", "RightToeBase"}
    preset = detect_skeleton_preset(bones)
    assert preset is not None
    assert preset.name == "mixamo"
    assert preset.mapping["pelvis"] == "Hips"


def test_unknown_skeletons_are_not_detected() -> None:
    assert detect_skeleton_preset({"Bone", "Bone.001", "Bone.002"}) is None


def test_mixamo_characters_skip_the_tpose_re_rest_and_ue_does_not() -> None:
    ue = detect_skeleton_preset({"thigh_l", "clavicle_l", "spine_05"})
    mixamo = detect_skeleton_preset({"mixamorig:Hips", "mixamorig:LeftUpLeg"})
    assert ue is not None and not ue.already_t_pose
    assert mixamo is not None and mixamo.already_t_pose


def test_t_pose_arms_measure_zero_deviation() -> None:
    left = arm_t_pose_deviation_degrees((0.15, 0.0, 1.5), (0.41, 0.0, 1.5), "l")
    right = arm_t_pose_deviation_degrees((-0.15, 0.0, 1.5), (-0.41, 0.0, 1.5), "r")
    assert left == pytest.approx(0.0, abs=1e-9)
    assert right == pytest.approx(0.0, abs=1e-9)


def test_drooped_arms_measure_their_droop_angle() -> None:
    # Field failure shape (task 0033): custom Mixamo uploads keep the uploaded
    # bind pose, commonly arms hanging ~70 degrees below horizontal.
    theta = math.radians(70.0)
    elbow = (0.15 + 0.26 * math.cos(theta), 0.0, 1.5 - 0.26 * math.sin(theta))
    deviation = arm_t_pose_deviation_degrees((0.15, 0.0, 1.5), elbow, "l")
    assert deviation == pytest.approx(70.0, abs=1e-6)


def test_forward_arms_measure_their_deviation_too() -> None:
    deviation = arm_t_pose_deviation_degrees((0.15, 0.0, 1.5), (0.15, -0.26, 1.5), "l")
    assert deviation == pytest.approx(90.0, abs=1e-6)


def test_deviation_threshold_stays_below_the_probe_failure_angle() -> None:
    # The probe tolerates PROBE_RELATIVE_TOLERANCE of the arm length, which a
    # small-angle droop crosses at ~2.9 degrees; the re-rest trigger must fire
    # before that so no character can both skip the re-rest and fail the probe.
    assert 0.0 < T_POSE_MAX_ARM_DEVIATION_DEGREES < math.degrees(PROBE_RELATIVE_TOLERANCE)


def _arm_lines(droop_degrees: float) -> dict:
    theta = math.radians(droop_degrees)
    lines = {}
    for side, sign in (("l", 1.0), ("r", -1.0)):
        shoulder = (sign * 0.15, 0.0, 1.5)
        elbow = (
            sign * (0.15 + 0.26 * math.cos(theta)),
            0.0,
            1.5 - 0.26 * math.sin(theta),
        )
        lines[side] = (shoulder, elbow)
    return lines


def test_a_preset_that_never_claims_t_pose_always_re_rests() -> None:
    assert needs_t_pose_re_rest(ue_preset(), _arm_lines(0.0))


def test_a_measured_t_pose_keeps_the_claimed_skip() -> None:
    assert not needs_t_pose_re_rest(mixamo_preset("mixamorig:"), _arm_lines(0.0))


def test_arms_past_the_threshold_invalidate_the_t_pose_claim() -> None:
    preset = mixamo_preset("mixamorig:")
    assert not needs_t_pose_re_rest(preset, _arm_lines(1.9))
    assert needs_t_pose_re_rest(preset, _arm_lines(2.1))
    assert needs_t_pose_re_rest(preset, _arm_lines(70.0))


def test_one_drooped_arm_is_enough_to_re_rest() -> None:
    lines = _arm_lines(0.0)
    lines["r"] = _arm_lines(70.0)["r"]
    assert needs_t_pose_re_rest(mixamo_preset("mixamorig:"), lines)


def test_validate_mapping_reports_missing_joints() -> None:
    partial = {name: name for name in SMPLX_BODY_JOINTS if not name.startswith("left_")}
    missing = validate_mapping(partial)
    assert missing and all(name.startswith("left_") for name in missing)


def test_probe_expectations_raise_lifts_and_swing_goes_behind() -> None:
    expected = probe_expectations(0.3)
    assert expected["raise_z"] == (-0.3, 0.0, 0.3)
    assert expected["swing_y"] == (-0.3, 0.3, 0.0)


def test_core_quaternion_has_parity_with_the_removed_addon_helper() -> None:
    # The converter's self-verification dropped its stdlib axis_angle_quaternion
    # for the single core implementation. Pin numeric parity to what the removed
    # helper produced: a +z quarter turn and the zero-vector identity.
    w, x, y, z = axis_angle_to_quaternion(np.array([0.0, 0.0, math.pi / 2]))
    assert w == pytest.approx(math.cos(math.pi / 4))
    assert z == pytest.approx(math.sin(math.pi / 4))
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(0.0)
    assert np.allclose(axis_angle_to_quaternion(np.zeros(3)), [1.0, 0.0, 0.0, 0.0])
