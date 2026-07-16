"""The PoseCap N-panel: composition of every panel section plus draw recovery."""

from __future__ import annotations

import logging
from typing import Any

from .capture_readiness import (
    body_models_ready_for_selected_backend,
    getting_started_steps,
    valid_target_armature,
)
from .character_setup_panel import draw_character_setup_section
from .instrumentation import configure_addon_logging
from .keyframe_manager import draw_keyframe_manager_section
from .live_stream_panel import draw_live_stream_panel
from .model_setup_panel import active_model_setup_session, draw_model_setup_status
from .onboarding import draw_getting_started, onboarding_complete
from .panel_text import context_wrap_chars
from .preferences_panel import ADDON_VERSION, addon_preferences
from .stream_properties import settings_from_context
from .support_panel import addon_log_path, draw_support_section

_LAST_PANEL_DRAW_FAILURE: tuple[type[BaseException], str] | None = None


def draw_main_panel(layout: Any, context: Any) -> None:
    """Draw the full PoseCap panel for the current scene state."""
    settings = settings_from_context(context)
    preferences = addon_preferences(context)
    header = layout.row(align=True)
    header.label(text=f"PoseCap {ADDON_VERSION}", icon="ARMATURE_DATA")
    header.prop(settings, "show_support", text="", icon="QUESTION")
    # Measure the panel so long status/hint text wraps to the actual width
    # instead of truncating (a non-technical user must read the whole message).
    wrap_chars = context_wrap_chars(context)
    # The Getting Started checklist is the first-run face: it renders whenever
    # onboarding is incomplete (never hidden by a single state edge, the failure
    # mode of the old conditional section) and collapses once every step is done.
    steps = getting_started_steps(context, settings)
    capture_ready = onboarding_complete(steps)
    if not capture_ready:
        draw_getting_started(layout, steps)
    # Model-download progress still needs a home once the wizard dialog closes:
    # the credential install runs in the background and its status lands here.
    session = active_model_setup_session()
    if session is not None:
        draw_model_setup_status(layout, session, wrap_chars=wrap_chars)
    draw_live_stream_panel(layout, settings, capture_ready=capture_ready, wrap_chars=wrap_chars)
    draw_character_setup_section(layout, settings)
    if valid_target_armature(settings) is not None:
        draw_keyframe_manager_section(layout, context.scene)
    draw_support_section(
        layout,
        context,
        settings,
        preferences,
        models_ready=body_models_ready_for_selected_backend(context),
    )


def build_main_panel_class(bpy_module: Any) -> type[Any]:
    """Build the PoseCap panel class against a bpy-like module."""

    class POSECAP_PT_LiveStream(bpy_module.types.Panel):
        bl_label = "PoseCap"
        bl_idname = "POSECAP_PT_live_stream"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "PoseCap"

        def draw(self, context: Any) -> None:
            global _LAST_PANEL_DRAW_FAILURE
            try:
                draw_main_panel(self.layout, context)
            except Exception as exc:
                _log_new_draw_failure(context, bpy_module, exc)
                self.layout.label(text="PoseCap could not refresh this panel.", icon="ERROR")
                self.layout.label(text="Your scene is safe.")
                self.layout.label(text="Create a Support Bundle to share the error.")
                actions = self.layout.row(align=True)
                actions.operator("posecap.create_support_bundle", text="Create Support Bundle")
                actions.operator("posecap.open_logs", text="Open Logs")
                return
            _LAST_PANEL_DRAW_FAILURE = None

    return POSECAP_PT_LiveStream


def reset_draw_failure_memory() -> None:
    """Forget the last logged draw failure (fresh registration starts clean)."""
    global _LAST_PANEL_DRAW_FAILURE
    _LAST_PANEL_DRAW_FAILURE = None


def _log_new_draw_failure(context: Any, bpy_module: Any, exc: BaseException) -> None:
    """Log a draw failure once until the panel recovers, file log preferred."""
    global _LAST_PANEL_DRAW_FAILURE
    failure = (type(exc), str(exc))
    if failure == _LAST_PANEL_DRAW_FAILURE:
        return
    _LAST_PANEL_DRAW_FAILURE = failure
    try:
        logger = configure_addon_logging(addon_log_path(context, bpy_module))
    except Exception:
        logging.getLogger("posecap_addon").error(
            "panel draw failed; file logging is unavailable",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return
    logger.exception("panel draw failed")
