from posecap_addon.panels import (
    SCENE_PROPERTY_NAME,
    draw_live_stream_panel,
    register_blender_ui,
    unregister_blender_ui,
)
from posecap_addon.ui_state import LifecycleState, lifecycle_controls


def test_lifecycle_controls_match_stream_state_machine() -> None:
    assert lifecycle_controls("STOPPED").can_start
    assert not lifecycle_controls("STOPPED").can_stop

    assert not lifecycle_controls("STARTING").can_start
    assert lifecycle_controls("STARTING").can_stop

    assert not lifecycle_controls("STREAMING").can_start
    assert lifecycle_controls("STREAMING").can_stop
    assert lifecycle_controls("STREAMING").can_record

    assert lifecycle_controls("RECORDING").is_recording
    assert lifecycle_controls("RECORDING").can_record

    assert lifecycle_controls("RECONNECTING").can_stop
    assert not lifecycle_controls("RECONNECTING").can_record

    warning = lifecycle_controls("WARNING", status_message="target armature is unavailable")
    assert warning.can_stop
    assert warning.status_text == "target armature is unavailable"


def test_live_stream_panel_draws_state_controls_from_lifecycle() -> None:
    layout = _FakeLayout()

    draw_live_stream_panel(layout, _Settings(lifecycle_state="STOPPED"))

    assert layout.enabled_for_operator("posecap.start_stream")
    assert not layout.enabled_for_operator("posecap.stop_stream")
    assert not layout.enabled_for_property("record_live_mocap")
    assert layout.has_property("target_armature")
    assert layout.has_label("Stopped")


def test_blender_ui_registration_adds_scene_state_and_unregisters_cleanly() -> None:
    bpy = _FakeBpy()

    register_blender_ui(bpy)

    assert [cls.__name__ for cls in bpy.utils.registered] == [
        "POSECAP_PG_LiveStreamSettings",
        "POSECAP_OT_StartStream",
        "POSECAP_OT_StopStream",
        "POSECAP_PT_LiveStream",
    ]
    assert getattr(bpy.types.Scene, SCENE_PROPERTY_NAME)[0] == "PointerProperty"

    unregister_blender_ui(bpy)
    unregister_blender_ui(bpy)

    assert not hasattr(bpy.types.Scene, SCENE_PROPERTY_NAME)
    assert [cls.__name__ for cls in bpy.utils.unregistered] == [
        "POSECAP_PT_LiveStream",
        "POSECAP_OT_StopStream",
        "POSECAP_OT_StartStream",
        "POSECAP_PG_LiveStreamSettings",
    ]


class _Settings:
    lifecycle_state: LifecycleState
    status_message: str

    def __init__(self, *, lifecycle_state: LifecycleState, status_message: str = "") -> None:
        self.lifecycle_state = lifecycle_state
        self.status_message = status_message
        self.target_armature = None
        self.camera_index = 0
        self.pear_root = ""
        self.record_live_mocap = False
        self.apply_orientation_fix = True


class _FakeLayout:
    def __init__(
        self,
        *,
        enabled: bool = True,
        operators: list[tuple[str, bool]] | None = None,
        properties: list[tuple[str, bool]] | None = None,
        labels: list[str] | None = None,
    ) -> None:
        self.enabled = enabled
        self._operators = [] if operators is None else operators
        self._properties = [] if properties is None else properties
        self._labels = [] if labels is None else labels

    def row(self, *, align: bool = False) -> "_FakeLayout":
        return _FakeLayout(
            enabled=self.enabled,
            operators=self._operators,
            properties=self._properties,
            labels=self._labels,
        )

    def column(self) -> "_FakeLayout":
        return self.row()

    def box(self) -> "_FakeLayout":
        return self.row()

    def label(self, *, text: str, icon: str = "NONE") -> None:
        self._labels.append(text)

    def prop(self, _data: object, property_name: str, **_kwargs: object) -> None:
        self._properties.append((property_name, self.enabled))

    def operator(self, operator_id: str, *, text: str = "", icon: str = "NONE") -> None:
        self._operators.append((operator_id, self.enabled))

    def enabled_for_operator(self, operator_id: str) -> bool:
        return self._enabled_for(operator_id, self._operators)

    def enabled_for_property(self, property_name: str) -> bool:
        return self._enabled_for(property_name, self._properties)

    def has_property(self, property_name: str) -> bool:
        return any(name == property_name for name, _enabled in self._properties)

    def has_label(self, text: str) -> bool:
        return text in self._labels

    @staticmethod
    def _enabled_for(name: str, values: list[tuple[str, bool]]) -> bool:
        matches = [enabled for value_name, enabled in values if value_name == name]
        if len(matches) != 1:
            raise AssertionError(f"expected one entry for {name}, got {matches}")
        return matches[0]


class _FakeBpy:
    def __init__(self) -> None:
        self.types = _FakeBpyTypes()
        self.props = _FakeBpyProps()
        self.utils = _FakeBpyUtils()


class _FakeBpyTypes:
    class PropertyGroup:
        pass

    class Panel:
        pass

    class Operator:
        pass

    class Object:
        pass

    class Scene:
        pass


class _FakeBpyProps:
    def EnumProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("EnumProperty", kwargs)

    def StringProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("StringProperty", kwargs)

    def IntProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("IntProperty", kwargs)

    def BoolProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("BoolProperty", kwargs)

    def PointerProperty(self, **kwargs: object) -> tuple[str, object]:
        return ("PointerProperty", kwargs)


class _FakeBpyUtils:
    def __init__(self) -> None:
        self.registered: list[type] = []
        self.unregistered: list[type] = []

    def register_class(self, cls: type) -> None:
        self.registered.append(cls)

    def unregister_class(self, cls: type) -> None:
        self.unregistered.append(cls)
