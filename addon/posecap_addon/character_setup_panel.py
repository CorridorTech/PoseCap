"""Character Setup panel section: one-click armature conversion.

The user picks a character armature, PoseCap detects the skeleton family
(Unreal Engine or Mixamo), converts it in the open file as a native
undoable operator, and reports the self-verification probe result. No
terminal, no subprocess — Ctrl+Z reverts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .character_setup import (
    SMPLX_BODY_JOINTS,
    ConversionError,
    SkeletonPreset,
    convert_armature,
    detect_skeleton_preset,
    mixamo_preset,
    ue_preset,
    validate_mapping,
)
from .panel_text import DEFAULT_WRAP_CHARS, draw_wrapped_label

CHARACTER_PRESET_ITEMS = (
    ("AUTO", "Auto-Detect", "Recognize the skeleton family from bone names"),
    ("UE", "Unreal Engine / Fortnite", "Unreal Engine humanoid skeleton"),
    ("MIXAMO", "Mixamo", "Mixamo skeleton (Adobe's free character library)"),
    ("CUSTOM", "Custom Mapping", "JSON file mapping SMPL-X joints to bone names"),
)


def draw_character_setup_section(layout: Any, settings: Any) -> None:
    """Draw the character conversion controls."""
    box = layout.box()
    box.label(text="Character Setup", icon="OUTLINER_OB_ARMATURE")
    armature = getattr(settings, "target_armature", None)
    if is_converted_armature(armature):
        box.label(text="Character ready for capture", icon="CHECKMARK")
        return
    column = box.column()
    if armature is None:
        draw_wrapped_label(
            column,
            "Import a character; PoseCap will select its armature.",
            chars=DEFAULT_WRAP_CHARS,
            icon="INFO",
        )
    column.prop(settings, "character_preset")
    if settings.character_preset == "CUSTOM":
        column.prop(settings, "character_mapping_json")
    column.operator(
        "posecap.convert_character",
        text="Convert Character for PoseCap",
        icon="ARMATURE_DATA",
    )


def build_character_setup_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Build the character-setup operator classes against a bpy-like module."""

    class POSECAP_OT_ConvertCharacter(bpy_module.types.Operator):
        bl_idname = "posecap.convert_character"
        bl_label = "Convert Character for PoseCap"
        bl_description = (
            "Rename and reorient the picked armature to the SMPL-X convention "
            "so live capture can drive it (undoable)"
        )
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context: Any) -> set[str]:
            settings = getattr(context.scene, "posecap", None)
            armature = _picked_armature(context, settings)
            if armature is None:
                self.report(
                    {"ERROR"},
                    "Pick a target armature first (or select one in the viewport).",
                )
                return {"CANCELLED"}
            try:
                preset = _resolve_preset(settings, armature)
                result = convert_armature(bpy_module, armature, preset)
            except ConversionError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            self.report(
                {"INFO"},
                f"Character ready ({preset.label}); verification {result.max_probe_error:.4f}",
            )
            return {"FINISHED"}

    return (POSECAP_OT_ConvertCharacter,)


def _picked_armature(context: Any, settings: Any) -> Any | None:
    armature = getattr(settings, "target_armature", None)
    if armature is not None and getattr(armature, "type", None) == "ARMATURE":
        return armature
    active = getattr(context, "active_object", None)
    if active is not None and getattr(active, "type", None) == "ARMATURE":
        return active
    return None


def _resolve_preset(settings: Any, armature: Any) -> SkeletonPreset:
    choice = str(getattr(settings, "character_preset", "AUTO"))
    if choice == "UE":
        return ue_preset()
    if choice == "MIXAMO":
        return _detected_mixamo(armature)
    if choice == "CUSTOM":
        return _custom_preset(str(getattr(settings, "character_mapping_json", "")))
    detected = detect_skeleton_preset(set(_bone_names(armature)))
    if detected is None:
        raise ConversionError(
            "Could not recognize this skeleton — choose a preset "
            "(Unreal Engine, Mixamo, or a custom mapping file)."
        )
    return detected


def _detected_mixamo(armature: Any) -> SkeletonPreset:
    detected = detect_skeleton_preset(set(_bone_names(armature)))
    if detected is not None and detected.name == "mixamo":
        return detected
    return mixamo_preset("mixamorig:")


def _custom_preset(mapping_path: str) -> SkeletonPreset:
    if mapping_path.strip() == "":
        raise ConversionError("Choose the custom mapping JSON file first.")
    try:
        raw_mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConversionError(f"Could not read the mapping file: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConversionError(f"The mapping file is not valid JSON: {exc}") from exc
    base = ue_preset()
    mapping = dict(base.mapping)
    mapping.update({str(key): str(value) for key, value in raw_mapping.items()})
    missing = validate_mapping(mapping)
    if missing:
        raise ConversionError(f"mapping is missing SMPL-X joints: {', '.join(missing)}")
    return SkeletonPreset(
        name="custom",
        label="Custom mapping",
        mapping=mapping,
        arm_chains=base.arm_chains,
        already_t_pose=base.already_t_pose,
    )


def _bone_names(armature: Any) -> tuple[str, ...]:
    bones: Any = armature.pose.bones
    keys = getattr(bones, "keys", None)
    if callable(keys):
        names: Any = keys()
        return tuple(str(name) for name in names)
    return tuple(str(getattr(bone, "name", "")) for bone in bones)


def is_converted_armature(armature: Any) -> bool:
    if armature is None:
        return False
    try:
        if getattr(armature, "type", None) != "ARMATURE":
            return False
        names = set(_bone_names(armature))
    except (AttributeError, ReferenceError):
        return False
    return set(SMPLX_BODY_JOINTS).issubset(names)
