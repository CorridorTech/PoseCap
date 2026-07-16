"""Scene-update sync: auto-select the obvious target armature safely.

Panel.draw runs in a read-only context, so any write to scene settings must
happen from Blender's depsgraph-update lifecycle instead. This module owns the
handler and the auto-selection policy.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .stream_properties import SCENE_PROPERTY_NAME, LiveStreamSettings

_SCENE_UPDATE_HANDLER: Callable[..., None] | None = None


def sync_scene_target(scene: Any, bpy_module: Any) -> None:
    """Persist the obvious target outside Panel.draw's read-only context."""
    if scene is None:
        return
    settings = getattr(scene, SCENE_PROPERTY_NAME, None)
    if settings is None:
        return
    context = getattr(bpy_module, "context", None)
    context_scene = getattr(context, "scene", None)
    active_object = getattr(context, "active_object", None) if context_scene is scene else None
    _auto_select_target_armature(scene, settings, active_object=active_object)


def register_scene_update_handler(bpy_module: Any) -> None:
    """Auto-select imported armatures from Blender's safe scene-update lifecycle."""
    global _SCENE_UPDATE_HANDLER
    if _SCENE_UPDATE_HANDLER is not None:
        return

    def sync_after_update(scene: Any, _depsgraph: Any = None) -> None:
        sync_scene_target(scene, bpy_module)

    handlers = bpy_module.app.handlers
    persistent = getattr(handlers, "persistent", lambda callback: callback)
    handler = persistent(sync_after_update)
    handlers.depsgraph_update_post.append(handler)
    _SCENE_UPDATE_HANDLER = handler


def unregister_scene_update_handler(bpy_module: Any) -> None:
    """Remove the scene-update callback without disturbing other add-ons."""
    global _SCENE_UPDATE_HANDLER
    handler = _SCENE_UPDATE_HANDLER
    if handler is None:
        return
    callbacks = bpy_module.app.handlers.depsgraph_update_post
    if handler in callbacks:
        callbacks.remove(handler)
    _SCENE_UPDATE_HANDLER = None


def _auto_select_target_armature(
    scene: Any,
    settings: LiveStreamSettings,
    *,
    active_object: Any = None,
) -> None:
    """Select the obvious armature automatically; ambiguous scenes stay manual."""
    try:
        selected = getattr(settings, "target_armature", None)
        if selected is not None and getattr(selected, "type", None) == "ARMATURE":
            return
    except ReferenceError:
        settings.target_armature = None
    try:
        if getattr(active_object, "type", None) == "ARMATURE":
            settings.target_armature = active_object
            return
    except ReferenceError:
        pass
    objects = getattr(scene, "objects", ())
    only_armature = None
    for obj in objects:
        try:
            if getattr(obj, "type", None) != "ARMATURE":
                continue
        except ReferenceError:
            continue
        if only_armature is not None:
            return
        only_armature = obj
    if only_armature is not None:
        settings.target_armature = only_armature
