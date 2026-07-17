"""Behavior tests for the public character-conversion entry point."""

from types import SimpleNamespace

import pytest
from posecap_addon.character_setup import (
    SMPLX_BODY_JOINTS,
    ConversionError,
    SkeletonPreset,
    convert_armature,
)


def _preset() -> SkeletonPreset:
    return SkeletonPreset(
        name="test",
        label="Test",
        mapping={joint: joint for joint in SMPLX_BODY_JOINTS},
        arm_chains={},
        already_t_pose=True,
    )


class _IdentityMatrix:
    """World matrix stand-in: identity transform, no mirroring."""

    is_negative = False

    def __matmul__(self, position):
        return position


def _armature_with_arms(*, left_elbow: tuple[float, float, float]) -> SimpleNamespace:
    heads = {joint: (0.0, 0.0, 1.0) for joint in SMPLX_BODY_JOINTS}
    heads["left_shoulder"] = (0.15, 0.0, 1.5)
    heads["right_shoulder"] = (-0.15, 0.0, 1.5)
    heads["left_elbow"] = left_elbow
    heads["right_elbow"] = (-0.41, 0.0, 1.5)
    bones = {joint: SimpleNamespace(head=head) for joint, head in heads.items()}
    return SimpleNamespace(
        name="CharacterRig",
        type="ARMATURE",
        matrix_world=_IdentityMatrix(),
        pose=SimpleNamespace(bones=bones),
    )


def _scene(armature, *, mesh_shape_keys) -> SimpleNamespace:
    mesh = SimpleNamespace(
        name="CharacterMesh",
        type="MESH",
        modifiers=[SimpleNamespace(type="ARMATURE", object=armature)],
        data=SimpleNamespace(shape_keys=mesh_shape_keys),
    )
    view_layer = SimpleNamespace(update=lambda: None)
    return SimpleNamespace(
        data=SimpleNamespace(objects=[armature, mesh]),
        context=SimpleNamespace(view_layer=view_layer),
    )


def test_convert_refuses_a_non_t_pose_character_with_shape_keys_before_mutating() -> None:
    # Task 0033: the T-pose claim is geometry-verified, and a re-rest that
    # cannot re-bind the mesh fails with the user's way out, before any rename
    # or reorient touches the asset.
    armature = _armature_with_arms(left_elbow=(0.15, 0.0, 1.24))  # arm hanging down
    bpy = _scene(armature, mesh_shape_keys=SimpleNamespace(key_blocks=[]))

    with pytest.raises(ConversionError) as raised:
        convert_armature(bpy, armature, _preset())

    message = str(raised.value)
    assert "shape keys" in message
    assert "T-pose" in message
    assert "convert again" in message


def test_convert_explains_when_the_selected_armature_does_not_deform_the_mesh() -> None:
    selected = SimpleNamespace(name="ControlRig", type="ARMATURE")
    character = SimpleNamespace(name="CharacterRig", type="ARMATURE")
    mesh = SimpleNamespace(
        name="CharacterMesh",
        type="MESH",
        modifiers=[SimpleNamespace(type="ARMATURE", object=character)],
    )
    bpy = SimpleNamespace(data=SimpleNamespace(objects=[selected, character, mesh]))

    with pytest.raises(ConversionError) as raised:
        convert_armature(bpy, selected, _preset())

    message = str(raised.value)
    assert "ControlRig" in message
    assert "CharacterRig" in message
    assert "Target Armature" in message


def test_convert_explains_how_to_bind_a_mesh_when_none_is_deforming() -> None:
    selected = SimpleNamespace(name="ControlRig", type="ARMATURE")
    bpy = SimpleNamespace(data=SimpleNamespace(objects=[selected]))

    with pytest.raises(ConversionError) as raised:
        convert_armature(bpy, selected, _preset())

    message = str(raised.value)
    assert "ControlRig" in message
    assert "Armature modifier" in message
