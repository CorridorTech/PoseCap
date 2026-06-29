"""Blender UI panel adapters for PoseCap live streaming."""

import importlib
from typing import Any, Protocol

from .ui_state import LIFECYCLE_STATE_ITEMS, LifecycleState, lifecycle_controls

SCENE_PROPERTY_NAME = "posecap"

_REGISTERED_CLASSES: tuple[type[Any], ...] = ()


class _LiveStreamSettings(Protocol):
    lifecycle_state: LifecycleState
    status_message: str


def draw_live_stream_panel(layout: Any, settings: _LiveStreamSettings) -> None:
    """Draw the live-stream controls from the current lifecycle state."""
    controls = lifecycle_controls(
        settings.lifecycle_state,
        status_message=settings.status_message,
    )

    box = layout.box()
    box.label(text=controls.status_text, icon="INFO")

    column = layout.column()
    column.prop(settings, "target_armature")
    column.prop(settings, "camera_index")
    column.prop(settings, "pear_root")
    column.prop(settings, "apply_orientation_fix")

    actions = layout.row(align=True)
    start = actions.row()
    start.enabled = controls.can_start
    start.operator("posecap.start_stream", text="Start Stream", icon="PLAY")

    stop = actions.row()
    stop.enabled = controls.can_stop
    stop.operator("posecap.stop_stream", text="Stop Stream", icon="PAUSE")

    record = layout.row()
    record.enabled = controls.can_record
    record.prop(settings, "record_live_mocap", toggle=True)


def register() -> None:
    """Register the Blender UI classes with the runtime bpy module."""
    register_blender_ui(importlib.import_module("bpy"))


def unregister() -> None:
    """Unregister the Blender UI classes from the runtime bpy module."""
    unregister_blender_ui(importlib.import_module("bpy"))


def register_blender_ui(bpy_module: Any) -> None:
    """Register PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    if _REGISTERED_CLASSES:
        return

    classes = _build_blender_classes(bpy_module)
    for cls in classes:
        bpy_module.utils.register_class(cls)
    setattr(
        bpy_module.types.Scene,
        SCENE_PROPERTY_NAME,
        bpy_module.props.PointerProperty(type=classes[0]),
    )
    _REGISTERED_CLASSES = classes


def unregister_blender_ui(bpy_module: Any) -> None:
    """Unregister PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    if hasattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME):
        delattr(bpy_module.types.Scene, SCENE_PROPERTY_NAME)
    if not _REGISTERED_CLASSES:
        return
    for cls in reversed(_REGISTERED_CLASSES):
        bpy_module.utils.unregister_class(cls)
    _REGISTERED_CLASSES = ()


def _build_blender_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    class POSECAP_PG_LiveStreamSettings(bpy_module.types.PropertyGroup):
        __slots__ = ()

    POSECAP_PG_LiveStreamSettings.__annotations__ = {
        "lifecycle_state": bpy_module.props.EnumProperty(
            name="State",
            description="Live stream lifecycle state",
            items=LIFECYCLE_STATE_ITEMS,
            default="STOPPED",
        ),
        "status_message": bpy_module.props.StringProperty(
            name="Status",
            description="Last stream lifecycle message",
            default="",
        ),
        "target_armature": bpy_module.props.PointerProperty(
            name="Target Armature",
            description="SMPL-X armature that receives live poses",
            type=bpy_module.types.Object,
            poll=_is_armature_object,
        ),
        "camera_index": bpy_module.props.IntProperty(
            name="Camera",
            description="Engine capture device index",
            default=0,
            min=0,
        ),
        "pear_root": bpy_module.props.StringProperty(
            name="PEAR Root",
            description="External PEAR checkout path",
            default="",
            subtype="DIR_PATH",
        ),
        "apply_orientation_fix": bpy_module.props.BoolProperty(
            name="PEAR Orientation Fix",
            description="Apply PoseCap's PEAR-to-SMPL-X orientation correction",
            default=True,
        ),
        "record_live_mocap": bpy_module.props.BoolProperty(
            name="Record Live MoCap",
            description="Insert keyframes for applied stream frames",
            default=False,
        ),
    }

    class POSECAP_OT_StartStream(bpy_module.types.Operator):
        bl_idname = "posecap.start_stream"
        bl_label = "Start Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return _settings_from_context(context).lifecycle_state == "STOPPED"

        def execute(self, context: Any) -> set[str]:
            settings = _settings_from_context(context)
            settings.lifecycle_state = "STARTING"
            settings.status_message = "Starting"
            return {"FINISHED"}

    class POSECAP_OT_StopStream(bpy_module.types.Operator):
        bl_idname = "posecap.stop_stream"
        bl_label = "Stop Stream"
        bl_options = {"REGISTER"}

        @classmethod
        def poll(cls, context: Any) -> bool:
            return lifecycle_controls(_settings_from_context(context).lifecycle_state).can_stop

        def execute(self, context: Any) -> set[str]:
            settings = _settings_from_context(context)
            settings.lifecycle_state = "STOPPED"
            settings.status_message = "Stopped"
            settings.record_live_mocap = False
            return {"FINISHED"}

    class POSECAP_PT_LiveStream(bpy_module.types.Panel):
        bl_label = "PoseCap"
        bl_idname = "POSECAP_PT_live_stream"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "PoseCap"

        def draw(self, context: Any) -> None:
            draw_live_stream_panel(self.layout, _settings_from_context(context))

    return (
        POSECAP_PG_LiveStreamSettings,
        POSECAP_OT_StartStream,
        POSECAP_OT_StopStream,
        POSECAP_PT_LiveStream,
    )


def _settings_from_context(context: Any) -> Any:
    return getattr(context.scene, SCENE_PROPERTY_NAME)


def _is_armature_object(_settings: Any, candidate: Any) -> bool:
    return getattr(candidate, "type", None) == "ARMATURE"
