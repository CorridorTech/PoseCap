"""Body Models panel section: guided setup UI for the licensed SMPL-X files.

The section only appears while models are missing (CK2P: the happy path
stays clean once setup is done). Credentials live on WindowManager
properties — Blender never saves those into .blend files — and the password
field is cleared the moment the download starts.
"""

from __future__ import annotations

import os
import time
from functools import partial
from pathlib import Path
from typing import Any

from .apply_timer import tag_view3d_redraw
from .model_setup import (
    ModelSetupSession,
    MpiCredentials,
    missing_model_assets,
    verify_models_with_doctor,
)
from .panel_text import DEFAULT_WRAP_CHARS, draw_wrapped_label
from .pear_root import resolve_pear_root

MODEL_SIGNUP_URLS = {
    "SMPL": "https://smpl.is.tue.mpg.de/register.php",
    "SMPL-X": "https://smpl-x.is.tue.mpg.de/register.php",
    "FLAME": "https://flame.is.tue.mpg.de/register.php",
}

_POLL_INTERVAL_SECONDS = 0.5
_MISSING_CACHE_TTL_SECONDS = 2.0

_ACTIVE_SESSION: ModelSetupSession | None = None
_MISSING_CACHE: dict[str, tuple[float, bool]] = {}


def active_model_setup_session() -> ModelSetupSession | None:
    """The setup session the panel is currently showing, if any."""
    return _ACTIVE_SESSION


def models_missing(pear_root: str) -> bool:
    """Cheap draw-time check whether required models are absent (2s cache)."""
    if pear_root == "":
        return False
    now = time.monotonic()
    cached = _MISSING_CACHE.get(pear_root)
    if cached is not None and now - cached[0] < _MISSING_CACHE_TTL_SECONDS:
        return cached[1]
    result = len(missing_model_assets(Path(pear_root))) > 0
    _MISSING_CACHE[pear_root] = (now, result)
    return result


def draw_model_setup_status(
    layout: Any, session: Any | None, *, wrap_chars: int = DEFAULT_WRAP_CHARS
) -> None:
    """Show model-download progress in the panel.

    The setup wizard is a transient dialog: once the user clicks OK the
    credential install runs in the background, so its status needs a home on
    the always-visible panel. Nothing renders while there is no active run.
    Status and error text wrap so a failure ("…does not contain
    SMPL_NEUTRAL.pkl. Please retry…") is fully readable, not truncated.
    """
    if session is None:
        return
    if session.state in ("RUNNING", "WATCHING"):
        box = layout.box()
        box.label(text="Body Models", icon="ARMATURE_DATA")
        fraction = getattr(session, "progress_fraction", None)
        if fraction is not None:
            # A real bar (Blender 4.0+ layout.progress) so the user sees the
            # download move instead of guessing whether it hung.
            box.progress(factor=float(fraction), type="BAR", text=session.status_message)
            return
        draw_wrapped_label(box, session.status_message, chars=wrap_chars, icon="TIME")
        return
    if session.state in ("DONE", "FAILED"):
        icon = "CHECKMARK" if session.state == "DONE" else "ERROR"
        draw_wrapped_label(layout.box(), session.status_message, chars=wrap_chars, icon=icon)


def draw_body_models_wizard(layout: Any, wm_group: Any) -> None:
    """The guided body-model setup form shown inside the setup wizard dialog.

    The dialog's OK button runs the credential download (the wizard operator's
    ``execute``); this only lays out the license step, credentials, and the
    manual-download alternative.
    """
    column = layout.column()
    column.label(text="PoseCap needs the licensed body models — a free, one-time setup.")
    if wm_group.status != "":
        column.label(text=wm_group.status, icon="INFO")
    column.label(text="1. Create free accounts (use the same email + password):")
    signup_row = column.row(align=True)
    for site_name, url in MODEL_SIGNUP_URLS.items():
        signup_row.operator("wm.url_open", text=site_name, icon="URL").url = url
    column.label(text="Signing up on the official sites is the license step.")
    column.label(text="2. Enter that email and password (never saved):")
    column.prop(wm_group, "mpi_email")
    column.prop(wm_group, "mpi_password")
    column.label(text="Click OK to download and install the models.")
    column.label(text="Prefer the browser? Download the files yourself, then:")
    column.operator(
        "posecap.watch_model_downloads",
        text="Watch my Downloads Folder",
        icon="VIEWZOOM",
    )


def build_model_setup_classes(bpy_module: Any) -> tuple[type[Any], ...]:
    """Build the model-setup operator classes against a bpy-like module."""

    class POSECAP_OT_SetupBodyModels(bpy_module.types.Operator):
        # The non-modal install entry: same pipeline as the wizard but no
        # dialog, so it runs under `blender --background` (headless e2e /
        # scripted installs) where invoke_props_dialog has no window to open.
        bl_idname = "posecap.setup_body_models"
        bl_label = "Download & Install Models"
        bl_description = (
            "Download the licensed body models from the official MPI sites "
            "with your own account (credentials are used in memory only)"
        )
        bl_options = {"REGISTER"}

        def execute(self, context: Any) -> set[str]:
            return _start_credential_install(self, context, bpy_module)

    class POSECAP_OT_SetupBodyModelsWizard(bpy_module.types.Operator):
        bl_idname = "posecap.setup_body_models_wizard"
        bl_label = "Set Up Body Models"
        bl_description = (
            "Guided one-time setup: create free accounts on the official model "
            "sites, then download the licensed body models with your own account"
        )
        bl_options = {"REGISTER"}

        def invoke(self, context: Any, _event: Any) -> set[str]:
            # A dedicated popup is the guided surface: one obvious dialog the
            # user cannot miss, over the same install pipeline as the operator.
            return context.window_manager.invoke_props_dialog(self, width=480)

        def draw(self, context: Any) -> None:
            wm_group = context.window_manager.posecap_model_setup
            draw_body_models_wizard(self.layout, wm_group)

        def execute(self, context: Any) -> set[str]:
            return _start_credential_install(self, context, bpy_module)

    class POSECAP_OT_WatchModelDownloads(bpy_module.types.Operator):
        bl_idname = "posecap.watch_model_downloads"
        bl_label = "Watch my Downloads Folder"
        bl_description = (
            "Download the model files manually from the official sites; "
            "PoseCap detects, checks, and installs them automatically"
        )
        bl_options = {"REGISTER"}

        def execute(self, context: Any) -> set[str]:
            wm_group = context.window_manager.posecap_model_setup
            pear_root = _resolve_pear_root(context)
            if pear_root == "":
                return _report_setup_cancelled(
                    self, wm_group, "Set the PEAR Root first (in the panel or preferences)."
                )
            wm_group.status = ""
            session = _new_session(context)
            session.start_watching(Path(pear_root), Path.home() / "Downloads")
            _start_session_poll(bpy_module)
            return {"FINISHED"}

    return (
        POSECAP_OT_SetupBodyModels,
        POSECAP_OT_WatchModelDownloads,
        POSECAP_OT_SetupBodyModelsWizard,
    )


def _start_credential_install(operator: Any, context: Any, bpy_module: Any) -> set[str]:
    """Start the background credential download shared by the operator and wizard."""
    wm_group = context.window_manager.posecap_model_setup
    pear_root = _resolve_pear_root(context)
    if pear_root == "":
        return _report_setup_cancelled(
            operator, wm_group, "Set the PEAR Root first (in the panel or preferences)."
        )
    email = str(wm_group.mpi_email).strip()
    password = str(wm_group.mpi_password)
    if email == "" or password == "":
        return _report_setup_cancelled(
            operator, wm_group, "Enter the email and password of your model account first."
        )
    credentials = MpiCredentials(email=email, password=password)
    wm_group.mpi_password = ""
    wm_group.status = ""
    session = _new_session(context)
    session.start_credential_install(Path(pear_root), credentials)
    _start_session_poll(bpy_module)
    return {"FINISHED"}


def _report_setup_cancelled(operator: Any, wm_group: Any, message: str) -> set[str]:
    """Surface a setup validation failure and cancel.

    The wizard is a transient popup that Blender dismisses the moment execute()
    returns, so a status label alone is invisible — the report() to Blender's
    info log/status bar is what a user actually sees (GUIDELINES §2.2)."""
    wm_group.status = message
    operator.report({"ERROR"}, message)
    return {"CANCELLED"}


def _new_session(context: Any) -> ModelSetupSession:
    global _ACTIVE_SESSION
    engine_executable = _resolve_engine_executable(context)
    _ACTIVE_SESSION = ModelSetupSession(
        verify=partial(verify_models_with_doctor, engine_executable=engine_executable)
        if engine_executable != ""
        else _verify_skipped,
    )
    return _ACTIVE_SESSION


def _verify_skipped(_pear_root: Path) -> str:
    return "Models installed (set the engine path to also run the doctor check)."


def _start_session_poll(bpy_module: Any) -> None:
    def poll() -> float | None:
        session = _ACTIVE_SESSION
        if session is None:
            return None
        session.tick()
        _publish_status(bpy_module, session)
        if session.state in ("DONE", "FAILED"):
            _MISSING_CACHE.clear()
            return None
        return _POLL_INTERVAL_SECONDS

    timers = bpy_module.app.timers
    timers.register(poll, first_interval=_POLL_INTERVAL_SECONDS)


def _publish_status(bpy_module: Any, session: Any) -> None:
    context = getattr(bpy_module, "context", None)
    window_manager = getattr(context, "window_manager", None)
    wm_group = getattr(window_manager, "posecap_model_setup", None)
    if wm_group is not None:
        wm_group.status = session.status_message
    if context is not None:
        tag_view3d_redraw(context)


def _resolve_pear_root(context: Any) -> str:
    """Resolve PEAR Root with the SAME fallback the engine uses.

    A clean install types nothing, so without the env + installer-default
    fallback the wizard/operator would fail "Set the PEAR Root first" even
    though the engine finds the pear checkout — the exact clean-install bug.
    """
    settings = getattr(context.scene, "posecap", None)
    preferences = _addon_preferences(context)
    return resolve_pear_root(settings, preferences, dict(os.environ), lambda path: path.exists())


def _resolve_engine_executable(context: Any) -> str:
    preferences = _addon_preferences(context)
    return str(getattr(preferences, "engine_executable", "")).strip()


def _addon_preferences(context: Any) -> Any | None:
    from .panels import ADDON_ID

    preferences = getattr(context, "preferences", None)
    addons = getattr(preferences, "addons", None)
    if addons is None:
        return None
    addon = addons.get(ADDON_ID) if hasattr(addons, "get") else None
    return getattr(addon, "preferences", None)
