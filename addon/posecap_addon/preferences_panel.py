"""Addon preferences: persistent defaults and installer-path autoconfiguration."""

from __future__ import annotations

import os
from typing import Any, Protocol

from .pear_root import PathExists, first_nonempty
from .support import addon_version, default_installation_paths

_MANIFEST_ADDON_ID = "posecap"
ADDON_ID = (
    __package__.removesuffix(".posecap_addon")
    if __package__ and __package__ != "posecap_addon"
    else _MANIFEST_ADDON_ID
)

_ADDON_VERSION = addon_version()


class AddonPreferences(Protocol):
    """The persistent addon-preference surface the panel and launcher read."""

    pear_root: str
    engine_executable: str


def addon_preferences(context: Any) -> AddonPreferences | None:
    """This addon's preferences from a Blender context, or ``None`` headless."""
    preferences = getattr(context, "preferences", None)
    addons = getattr(preferences, "addons", None)
    if addons is None:
        return None
    addon = addons.get(ADDON_ID) if hasattr(addons, "get") else None
    if addon is None:
        return None
    return getattr(addon, "preferences", None)


def draw_addon_preferences(layout: Any, preferences: AddonPreferences) -> None:
    """Draw persistent addon defaults."""
    layout.label(text=f"PoseCap {_ADDON_VERSION}", icon="INFO")
    layout.label(text="Paths are detected automatically. Change them only for a custom install.")
    layout.prop(preferences, "pear_root")
    layout.prop(preferences, "engine_executable")


def autoconfigure_preferences(
    preferences: AddonPreferences | None,
    *,
    environ: dict[str, str] | None = None,
    path_exists: PathExists | None = None,
) -> None:
    """Persist detected installer paths without replacing explicit user choices."""
    if preferences is None:
        return
    env = environ if environ is not None else dict(os.environ)
    exists = path_exists if path_exists is not None else (lambda path: path.exists())
    installed = default_installation_paths(env)
    if installed is None:
        return
    if not first_nonempty(getattr(preferences, "pear_root", "")) and exists(installed.pear_root):
        preferences.pear_root = str(installed.pear_root)
    engine_setting = first_nonempty(getattr(preferences, "engine_executable", ""))
    if engine_setting in {"", "posecap-engine"} and exists(installed.engine_executable):
        preferences.engine_executable = str(installed.engine_executable)


def build_addon_preferences_class(bpy_module: Any) -> type[Any]:
    """Build the AddonPreferences class against a bpy-like module."""

    class POSECAP_AP_AddonPreferences(bpy_module.types.AddonPreferences):
        __slots__ = ()

        bl_idname = ADDON_ID
        bl_label = "PoseCap"

        def draw(self, _context: Any) -> None:
            draw_addon_preferences(self.layout, self)

    POSECAP_AP_AddonPreferences.__annotations__ = {
        "pear_root": bpy_module.props.StringProperty(
            name="Default PEAR Root",
            description="Default external PEAR checkout path for new live streams",
            default="",
            subtype="DIR_PATH",
        ),
        "engine_executable": bpy_module.props.StringProperty(
            name="Engine Executable",
            description="Command or absolute path used to launch the PoseCap engine",
            default="posecap-engine",
            subtype="FILE_PATH",
        ),
    }
    return POSECAP_AP_AddonPreferences
