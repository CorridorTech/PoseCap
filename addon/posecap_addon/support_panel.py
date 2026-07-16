"""Help & Support surface: logs access, support bundle, and the panel section."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .capture_readiness import panel_pear_root
from .pear_root import resolve_engine_executable
from .preferences_panel import ADDON_VERSION, AddonPreferences, addon_preferences
from .stream_properties import LiveStreamSettings, settings_from_context
from .support import (
    create_support_bundle,
    default_installation_paths,
    diagnostic_summary,
    resolve_logs_directory,
)


def logs_directory(context: Any, bpy_module: Any) -> Path:
    """The shared addon/engine logs directory for this installation."""
    preferences = addon_preferences(context)
    tempdir = str(getattr(bpy_module.app, "tempdir", "")).strip()
    return resolve_logs_directory(
        preferences,
        dict(os.environ),
        temp_directory=tempdir or tempfile.gettempdir(),
    )


def addon_log_path(context: Any, bpy_module: Any) -> Path:
    """The addon's rotating log file inside the shared logs directory."""
    return logs_directory(context, bpy_module) / "posecap-addon.log"


def draw_support_section(
    layout: Any,
    context: Any,
    settings: LiveStreamSettings,
    preferences: AddonPreferences | None,
    *,
    models_ready: bool,
) -> None:
    """Draw compact support tools with technical paths behind disclosure."""
    if not bool(getattr(settings, "show_support", False)):
        return
    box = layout.box()
    box.label(text="Help & Support", icon="QUESTION")
    installed = default_installation_paths(dict(os.environ))
    engine = resolve_engine_executable(
        preferences,
        dict(os.environ),
        lambda path: path.exists(),
    )
    runtime_ready = Path(engine).is_file()
    box.label(
        text="Runtime ready" if runtime_ready else "Runtime needs repair",
        icon="CHECKMARK" if runtime_ready else "ERROR",
    )
    box.label(
        text="Body models ready" if models_ready else "Body models need setup",
        icon="CHECKMARK" if models_ready else "ERROR",
    )
    actions = box.row(align=True)
    actions.operator("posecap.open_logs", text="Open Logs", icon="FILE_FOLDER")
    actions.operator("posecap.create_support_bundle", text="Support Bundle", icon="PACKAGE")
    box.label(text="The bundle stays on this computer until you share it.", icon="INFO")
    if preferences is not None:
        paths = box.column()
        paths.label(text="Installation Paths", icon="SETTINGS")
        paths.prop(preferences, "pear_root")
        paths.prop(preferences, "engine_executable")
        return
    if installed is None:
        box.label(text="PoseCap installation was not detected.", icon="ERROR")


def build_support_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Build the support operator classes against a bpy-like module."""

    class POSECAP_OT_OpenLogs(bpy_module.types.Operator):
        bl_idname = "posecap.open_logs"
        bl_label = "Open Logs Folder"
        bl_description = "Open the folder containing PoseCap setup, addon, and engine logs"
        bl_options = {"REGISTER"}

        def execute(self, context: Any) -> set[str]:
            try:
                logs = logs_directory(context, bpy_module)
                logs.mkdir(parents=True, exist_ok=True)
                bpy_module.ops.wm.path_open(filepath=str(logs))
            except Exception as exc:
                self.report({"ERROR"}, f"Could not open the logs folder: {exc}")
                return {"CANCELLED"}
            return {"FINISHED"}

    class POSECAP_OT_CreateSupportBundle(bpy_module.types.Operator):
        bl_idname = "posecap.create_support_bundle"
        bl_label = "Create Support Bundle"
        bl_description = "Create a local zip with PoseCap diagnostics and logs; nothing is uploaded"
        bl_options = {"REGISTER"}

        def execute(self, context: Any) -> set[str]:
            try:
                bundle = _write_support_bundle(context, bpy_module)
                context.window_manager.clipboard = str(bundle)
                bpy_module.ops.wm.path_open(filepath=str(bundle.parent))
            except Exception as exc:
                self.report({"ERROR"}, f"Could not create the Support Bundle: {exc}")
                return {"CANCELLED"}
            self.report(
                {"INFO"},
                "Support bundle created. Its path was copied to the clipboard.",
            )
            return {"FINISHED"}

    return (POSECAP_OT_OpenLogs, POSECAP_OT_CreateSupportBundle)


def _write_support_bundle(context: Any, bpy_module: Any) -> Path:
    """Collect diagnostics and logs into a zip next to the user's downloads."""
    settings = settings_from_context(context)
    preferences = addon_preferences(context)
    env = dict(os.environ)
    logs = logs_directory(context, bpy_module)
    pear_root = panel_pear_root(context)
    engine = resolve_engine_executable(
        preferences,
        env,
        lambda path: path.exists(),
    )
    diagnostics = diagnostic_summary(
        version=ADDON_VERSION,
        blender_version=".".join(str(part) for part in bpy_module.app.version),
        lifecycle_state=str(settings.lifecycle_state),
        pear_root=pear_root,
        engine_executable=engine,
        logs_directory=logs,
    )
    downloads = Path.home() / "Downloads"
    destination = downloads if downloads.is_dir() else Path(tempfile.gettempdir())
    return create_support_bundle(
        destination_directory=destination,
        logs_directory=logs,
        diagnostics=diagnostics,
    )
