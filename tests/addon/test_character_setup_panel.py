"""Behavior tests for the Character Setup panel section and operator."""

from types import SimpleNamespace

import posecap_addon.character_setup_panel as character_setup_panel
from posecap_addon.character_setup import (
    SMPLX_BODY_JOINTS,
    ConversionError,
    ConversionResult,
)
from posecap_addon.character_setup_panel import (
    build_character_setup_classes,
    draw_character_setup_section,
)


class _FakeLayout:
    def __init__(self, sink=None) -> None:
        self._sink = sink if sink is not None else {"operators": [], "props": [], "labels": []}

    def row(self, **_kwargs):
        return _FakeLayout(self._sink)

    def column(self, **_kwargs):
        return _FakeLayout(self._sink)

    def box(self):
        return _FakeLayout(self._sink)

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self._sink["labels"].append(text)

    def prop(self, _data, name: str, **_kwargs) -> None:
        self._sink["props"].append(name)

    def operator(self, operator_id: str, **_kwargs):
        self._sink["operators"].append(operator_id)
        return SimpleNamespace(url="")

    @property
    def operator_ids(self):
        return self._sink["operators"]

    @property
    def props_drawn(self):
        return self._sink["props"]


def _settings(preset: str = "AUTO") -> SimpleNamespace:
    return SimpleNamespace(
        character_preset=preset,
        character_mapping_json="",
        target_armature=None,
    )


def test_section_offers_preset_choice_and_convert_button() -> None:
    layout = _FakeLayout()

    draw_character_setup_section(layout, _settings())

    assert "posecap.convert_character" in layout.operator_ids
    assert "character_preset" in layout.props_drawn
    assert "character_mapping_json" not in layout.props_drawn


def test_custom_preset_reveals_the_mapping_file_field() -> None:
    layout = _FakeLayout()

    draw_character_setup_section(layout, _settings(preset="CUSTOM"))

    assert "character_mapping_json" in layout.props_drawn


def test_converted_character_shows_ready_state_instead_of_convert_again() -> None:
    layout = _FakeLayout()
    settings = _settings()
    settings.target_armature = _Armature(SMPLX_BODY_JOINTS)

    draw_character_setup_section(layout, settings)

    assert "posecap.convert_character" not in layout.operator_ids
    assert "Character ready for capture" in layout._sink["labels"]


def test_partially_named_character_still_offers_conversion() -> None:
    layout = _FakeLayout()
    settings = _settings()
    settings.target_armature = _Armature(("pelvis", "left_shoulder", "left_elbow"))

    draw_character_setup_section(layout, settings)

    assert "posecap.convert_character" in layout.operator_ids


def test_removed_character_degrades_to_setup_instead_of_breaking_panel_draw() -> None:
    layout = _FakeLayout()
    settings = _settings()
    settings.target_armature = _RemovedArmature()

    draw_character_setup_section(layout, settings)

    assert "posecap.convert_character" in layout.operator_ids


class _Operator:
    def __init__(self) -> None:
        self.reports: list[tuple[set[str], str]] = []

    def report(self, levels: set[str], message: str) -> None:
        self.reports.append((levels, message))


def _bpy_module() -> SimpleNamespace:
    return SimpleNamespace(types=SimpleNamespace(Operator=_Operator))


class _Armature:
    type = "ARMATURE"

    def __init__(self, bone_names: tuple[str, ...]) -> None:
        self.pose = SimpleNamespace(bones={name: object() for name in bone_names})
        self.data = SimpleNamespace(bones={name: object() for name in bone_names})


class _RemovedArmature:
    @property
    def type(self):
        raise ReferenceError("StructRNA of type Object has been removed")


def _context(armature) -> SimpleNamespace:
    return SimpleNamespace(
        scene=SimpleNamespace(
            posecap=SimpleNamespace(
                character_preset="AUTO",
                character_mapping_json="",
                target_armature=armature,
            )
        ),
        active_object=None,
        window_manager=SimpleNamespace(windows=[]),
    )


def test_convert_operator_is_undoable() -> None:
    (convert_cls,) = build_character_setup_classes(_bpy_module())
    assert "UNDO" in convert_cls.bl_options


def test_convert_reports_the_probe_result_on_success(monkeypatch) -> None:
    (convert_cls,) = build_character_setup_classes(_bpy_module())
    armature = _Armature(("mixamorig:Hips", "mixamorig:LeftUpLeg", "mixamorig:LeftForeArm"))
    conversions: list[tuple[object, SimpleNamespace]] = []

    def fake_convert(bpy, arm_obj, preset, **kwargs):
        conversions.append((arm_obj, preset))
        return ConversionResult(probe_lines=("probe raise_z …",), max_probe_error=0.0002)

    monkeypatch.setattr(character_setup_panel, "convert_armature", fake_convert)
    operator = convert_cls()

    result = operator.execute(_context(armature))

    assert result == {"FINISHED"}
    assert conversions and conversions[0][0] is armature
    assert conversions[0][1].name == "mixamo"
    assert any("0.0002" in message for _levels, message in operator.reports)


def test_convert_without_an_armature_is_a_friendly_cancel(monkeypatch) -> None:
    (convert_cls,) = build_character_setup_classes(_bpy_module())
    operator = convert_cls()

    result = operator.execute(_context(None))

    assert result == {"CANCELLED"}
    assert any("armature" in message.lower() for _levels, message in operator.reports)


def test_convert_with_an_unrecognized_skeleton_asks_for_a_preset(monkeypatch) -> None:
    (convert_cls,) = build_character_setup_classes(_bpy_module())
    armature = _Armature(("Bone", "Bone.001"))
    operator = convert_cls()

    result = operator.execute(_context(armature))

    assert result == {"CANCELLED"}
    assert any(
        "recognize" in message.lower() or "preset" in message.lower()
        for _levels, message in operator.reports
    )


def test_conversion_failures_surface_as_error_reports_not_tracebacks(monkeypatch) -> None:
    (convert_cls,) = build_character_setup_classes(_bpy_module())
    armature = _Armature(("thigh_l", "clavicle_l"))

    def failing_convert(bpy, arm_obj, preset, **kwargs):
        raise ConversionError("the armature is missing expected bones: hand_l")

    monkeypatch.setattr(character_setup_panel, "convert_armature", failing_convert)
    operator = convert_cls()

    result = operator.execute(_context(armature))

    assert result == {"CANCELLED"}
    assert any("hand_l" in message for _levels, message in operator.reports)
