"""Blender UI registration for PoseCap: the thin aggregator.

Each panel section, operator family, and PropertyGroup lives in its own
module exposing a ``build_*`` factory (the repo-wide pattern); this module
only composes them, in the registration order bpy requires: PropertyGroups
before any ``PointerProperty`` that uses them, panels after the operators
they reference, and unregistration as the exact reverse mirror.
"""

from __future__ import annotations

import importlib
from typing import Any

from .character_setup_panel import build_character_setup_classes
from .keyframe_manager import (
    KEY_POSES_INDEX_PROPERTY,
    KEY_POSES_PROPERTY,
    build_keyframe_manager_classes,
)
from .live_stream_panel import draw_live_stream_panel
from .main_panel import build_main_panel_class, reset_draw_failure_memory
from .model_setup_panel import build_model_setup_classes
from .preferences_panel import (
    ADDON_ID,
    addon_preferences,
    autoconfigure_preferences,
    build_addon_preferences_class,
    draw_addon_preferences,
)
from .recording import build_recording_classes
from .scene_sync import (
    register_scene_update_handler,
    sync_scene_target,
    unregister_scene_update_handler,
)
from .stream_operators import build_stream_operator_classes
from .stream_properties import (
    SCENE_PROPERTY_NAME,
    WM_MODEL_SETUP_PROPERTY_NAME,
    build_live_stream_settings_class,
    build_model_setup_property_group,
)
from .stream_session import stop_active_session
from .support_panel import build_support_classes

__all__ = [
    "ADDON_ID",
    "SCENE_PROPERTY_NAME",
    "WM_MODEL_SETUP_PROPERTY_NAME",
    "draw_addon_preferences",
    "draw_live_stream_panel",
    "register",
    "register_blender_ui",
    "unregister",
    "unregister_blender_ui",
]

_REGISTERED_CLASSES: tuple[type[Any], ...] = ()


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

    reset_draw_failure_memory()
    classes = _build_blender_classes(bpy_module)
    for cls in classes:
        bpy_module.utils.register_class(cls)
    setattr(
        bpy_module.types.Scene,
        SCENE_PROPERTY_NAME,
        bpy_module.props.PointerProperty(type=classes[0]),
    )
    model_setup_group = next(cls for cls in classes if cls.__name__ == "POSECAP_PG_ModelSetup")
    setattr(
        bpy_module.types.WindowManager,
        WM_MODEL_SETUP_PROPERTY_NAME,
        bpy_module.props.PointerProperty(type=model_setup_group),
    )
    key_pose_item = next(cls for cls in classes if cls.__name__ == "POSECAP_PG_KeyPoseItem")
    setattr(
        bpy_module.types.Scene,
        KEY_POSES_PROPERTY,
        bpy_module.props.CollectionProperty(type=key_pose_item),
    )
    setattr(
        bpy_module.types.Scene,
        KEY_POSES_INDEX_PROPERTY,
        bpy_module.props.IntProperty(default=0),
    )
    _REGISTERED_CLASSES = classes
    register_scene_update_handler(bpy_module)
    context = getattr(bpy_module, "context", None)
    if context is not None:
        autoconfigure_preferences(addon_preferences(context))
        sync_scene_target(getattr(context, "scene", None), bpy_module)


def unregister_blender_ui(bpy_module: Any) -> None:
    """Unregister PoseCap UI classes against a bpy-like module."""
    global _REGISTERED_CLASSES
    stop_active_session(bpy_module)
    unregister_scene_update_handler(bpy_module)
    for scene_property in (SCENE_PROPERTY_NAME, KEY_POSES_PROPERTY, KEY_POSES_INDEX_PROPERTY):
        if hasattr(bpy_module.types.Scene, scene_property):
            delattr(bpy_module.types.Scene, scene_property)
    if hasattr(bpy_module.types.WindowManager, WM_MODEL_SETUP_PROPERTY_NAME):
        delattr(bpy_module.types.WindowManager, WM_MODEL_SETUP_PROPERTY_NAME)
    if not _REGISTERED_CLASSES:
        return
    for cls in reversed(_REGISTERED_CLASSES):
        bpy_module.utils.unregister_class(cls)
    _REGISTERED_CLASSES = ()


def _build_blender_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Compose every PoseCap bpy class in its required registration order."""
    return (
        build_live_stream_settings_class(bpy_module),
        build_model_setup_property_group(bpy_module),
        build_addon_preferences_class(bpy_module),
        *build_stream_operator_classes(bpy_module),
        *build_support_classes(bpy_module),
        *build_model_setup_classes(bpy_module),
        *build_character_setup_classes(bpy_module),
        *build_recording_classes(bpy_module),
        *build_keyframe_manager_classes(bpy_module),
        build_main_panel_class(bpy_module),
    )
