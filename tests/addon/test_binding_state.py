"""Behavior tests for persisted non-destructive binding state."""

import numpy as np
from posecap_addon.binding_state import clear_binding, load_binding, store_binding
from posecap_core import BoundBone, PoseBinding


def _binding() -> PoseBinding:
    identity = np.asarray([1.0, 0.0, 0.0, 0.0])
    return PoseBinding({"pelvis": BoundBone("Hips", identity, identity)})


def test_binding_state_round_trips_through_an_armature_custom_property() -> None:
    armature: dict[str, str] = {}

    store_binding(armature, _binding())

    restored = load_binding(armature)

    assert restored is not None
    assert restored.bones["pelvis"].target_bone_name == "Hips"
    assert np.array_equal(restored.bones["pelvis"].compensation_quaternion, [1.0, 0.0, 0.0, 0.0])


def test_clear_binding_removes_only_posecap_binding_state() -> None:
    armature: dict[str, str] = {"artist_note": "keep me"}
    store_binding(armature, _binding())

    clear_binding(armature)

    assert load_binding(armature) is None
    assert armature == {"artist_note": "keep me"}
