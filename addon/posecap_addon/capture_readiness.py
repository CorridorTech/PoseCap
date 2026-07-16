"""Capture-readiness checks shared by the main panel and the stream operators.

The panel's onboarding checklist, the Start Stream poll gate, and the
operator's execute-time validation must agree, or a user gets an enabled
button that fails (the POC failure mode). Every reader goes through the
single checks in this module.
"""

from __future__ import annotations

import os
from typing import Any

from posecap_contracts import PoseBackendManifest

from .backend_registry import BackendSelectionError, discover_installed_pose_backends
from .character_setup_panel import is_converted_armature
from .model_setup_panel import models_missing
from .onboarding import onboarding_steps
from .pear_root import PathExists, resolve_pear_root
from .preferences_panel import addon_preferences
from .stream_properties import resolve_selected_backend, settings_from_context


def getting_started_steps(context: Any, settings: Any) -> Any:
    """The onboarding steps for the current scene, from live readiness checks."""
    # Resolve with the SAME fallback the engine uses (explicit -> env ->
    # installer default), or a fresh install reads as "no models" incorrectly.
    models_ready = body_models_ready_for_selected_backend(context)
    return onboarding_steps(
        models_ready=models_ready,
        character_ready=character_ready(settings),
    )


def character_ready(settings: Any) -> bool:
    """True when the selected armature follows the PoseCap convention.

    Guards a removed StructRNA: the panel redraws every frame, and reading
    ``.type`` on an armature deleted mid-session raises (AGENTS.md gotcha)."""
    return is_converted_armature(valid_target_armature(settings))


def valid_target_armature(settings: Any) -> Any | None:
    """Read a target safely without mutating a removed Blender RNA pointer."""
    try:
        armature = getattr(settings, "target_armature", None)
        return armature if getattr(armature, "type", None) == "ARMATURE" else None
    except ReferenceError:
        return None


def panel_pear_root(
    context: Any,
    *,
    environ: dict[str, str] | None = None,
    path_exists: PathExists | None = None,
) -> str:
    """Draw-time PEAR Root using the full engine fallback (installer default too)."""
    settings = settings_from_context(context)
    preferences = addon_preferences(context)
    env = environ if environ is not None else dict(os.environ)
    exists = path_exists if path_exists is not None else (lambda path: path.exists())
    return resolve_pear_root(settings, preferences, env, exists)


def body_models_ready_for_selected_backend(context: Any) -> bool:
    """A backend that does not use SMPL-X assets must not inherit PEAR setup."""
    try:
        backend = resolve_selected_backend(settings_from_context(context))
    except BackendSelectionError:
        catalog = discover_installed_pose_backends(dict(os.environ))
        if any(not item.manifest.requires_body_models for item in catalog.ready):
            return True
        return not models_missing(panel_pear_root(context))
    if backend is not None and not backend.requires_body_models:
        return True
    return not models_missing(panel_pear_root(context))


def capture_setup_issue(
    context: Any,
    settings: Any,
    backend_manifest: PoseBackendManifest | None = None,
) -> str | None:
    """The user-facing setup gap blocking capture, or ``None`` when ready."""
    if not character_ready(settings):
        return "Import and convert a character before starting capture."
    if (backend_manifest is None or backend_manifest.requires_body_models) and models_missing(
        panel_pear_root(context)
    ):
        return "Set up the PoseCap body models before starting capture."
    return None


def can_start_stream(context: Any) -> bool:
    """Keep Blender's enablement rule aligned with the selected backend's setup needs."""
    settings = settings_from_context(context)
    if settings.lifecycle_state != "STOPPED":
        return False
    try:
        backend_manifest = resolve_selected_backend(settings)
    except BackendSelectionError:
        return False
    return capture_setup_issue(context, settings, backend_manifest) is None
