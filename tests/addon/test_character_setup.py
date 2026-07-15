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
