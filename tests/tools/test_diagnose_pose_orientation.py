import importlib.util
import math
from pathlib import Path


def _load_pose_orientation_diagnostic_module():
    module_path = Path(__file__).parents[2] / "tools" / "diagnose_pose_orientation.py"
    spec = importlib.util.spec_from_file_location("diagnose_pose_orientation", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_left_arm_raise_diagnostic_pins_posecap_to_poc_quaternion_path() -> None:
    diagnostic = _load_pose_orientation_diagnostic_module()

    report = diagnostic.left_arm_raise_report()

    assert report["diagnostic_pose"] == "left_shoulder_positive_z"
    assert report["matches_poc"] is True
    assert report["non_identity_bones"] == ["pelvis", "left_shoulder"]
    assert report["bone_reports"]["left_shoulder"]["axis_angle"] == [
        0.0,
        0.0,
        math.pi / 2.0,
    ]
    assert (
        report["bone_reports"]["left_shoulder"]["posecap_quaternion"]
        == report["bone_reports"]["left_shoulder"]["poc_quaternion"]
    )
