"""Live-stream session runtime: the apply-timer loop and its lifecycle state.

One session owns the engine process, the TCP client, and the bpy timer that
applies frames. Every teardown path funnels through ``LiveStreamSession.stop``
so no later stream can inherit recording state (the POC's exact defect).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from .apply_timer import BpyArmaturePoseWriter, PoseApplyTimer, tag_view3d_redraw
from .stream_properties import LiveStreamSettings

_RECONNECTABLE_STATES = frozenset({"STREAMING", "RECORDING"})

# The installer pre-fetches the pinned PEAR pose weight during setup, so on an
# installed machine the first Start Stream only warms up the engine (a cold
# torch/pytorch3d load can take a minute or two). Without this hint the panel
# sits on "Starting" and a non-technical user assumes it hung (Corridor field
# report, 2026-07-10).
_LONG_START_SECONDS = 10.0
_LONG_START_MESSAGE = (
    "Still starting — the first run warms up the engine and can take a minute or two"
)

_ACTIVE_SESSION: LiveStreamSession | None = None


def _now() -> float:
    return time.monotonic()


def active_stream_session() -> LiveStreamSession | None:
    """The live-stream session currently driving the apply timer, if any."""
    return _ACTIVE_SESSION


def activate_stream_session(session: LiveStreamSession) -> None:
    """Make ``session`` the one ``stop_active_session`` tears down."""
    global _ACTIVE_SESSION
    _ACTIVE_SESSION = session


def stop_active_session(bpy_module: Any) -> None:
    """Stop and forget the active session; safe to call when none is active."""
    global _ACTIVE_SESSION
    session = _ACTIVE_SESSION
    _ACTIVE_SESSION = None
    if session is not None:
        session.stop(unregister_timer=True, bpy_module=bpy_module)


class LiveTargetArmaturePoseWriter:
    """Pose writer that re-reads the target armature setting on every apply."""

    def __init__(
        self,
        settings: LiveStreamSettings,
        *,
        redraw: Callable[[], None] | None = None,
    ) -> None:
        self._settings = settings
        self._redraw = redraw

    def is_valid(self) -> bool:
        return self._writer().is_valid()

    def apply(self, plan: Any, *, insert_keyframes: bool) -> None:
        self._writer().apply(plan, insert_keyframes=insert_keyframes)

    def tag_redraw(self) -> None:
        if self._redraw is not None:
            self._redraw()

    def _writer(self) -> BpyArmaturePoseWriter:
        return BpyArmaturePoseWriter(self._settings.target_armature)


class LifecyclePoseStream:
    """Frame source that advances the lifecycle state on the first frames."""

    def __init__(self, client: Any, settings: LiveStreamSettings) -> None:
        self._client = client
        self._settings = settings

    def latest(self) -> Any | None:
        frame = self._client.latest()
        if frame is not None and self._settings.lifecycle_state == "STARTING":
            self._settings.lifecycle_state = "STREAMING"
            self._settings.status_message = "Streaming"
        if (
            frame is not None
            and self._settings.lifecycle_state == "RECONNECTING"
            and getattr(self._client, "connection_state", "CONNECTED") == "CONNECTED"
        ):
            self._settings.lifecycle_state = "STREAMING"
            self._settings.status_message = "Streaming"
        return frame

    def close(self) -> None:
        self._client.close()


class LiveStreamSession:
    """The engine process + TCP client + bpy apply timer of one live stream."""

    def __init__(
        self,
        bpy_module: Any,
        settings: LiveStreamSettings,
        engine: Any,
        client: Any,
        timer: PoseApplyTimer,
    ) -> None:
        self._bpy_module = bpy_module
        self._settings = settings
        self._engine = engine
        self._client = client
        self._timer = timer
        self._stopped = False
        self._started_at = _now()
        self.timer_callback: Callable[[], float | None] = self._tick

    def _tick(self) -> float | None:
        if self._stopped:
            return None
        if not bool(getattr(self._engine, "running", True)):
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            self._settings.lifecycle_state = "STOPPED"
            self._settings.status_message = "Engine process exited (see posecap-engine.log)"
            return None
        if (
            getattr(self._client, "connection_state", None) == "RECONNECTING"
            and self._settings.lifecycle_state in _RECONNECTABLE_STATES
        ):
            self._settings.lifecycle_state = "RECONNECTING"
            self._settings.status_message = "Reconnecting"
        stream_error = getattr(self._client, "error", None)
        if stream_error is not None:
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            status = _stream_error_status(self._settings.lifecycle_state, stream_error)
            self._settings.lifecycle_state = "STOPPED"
            self._settings.status_message = status
            return None
        try:
            result = self._timer.tick()
        except Exception as exc:
            # bpy silently unregisters a timer whose callback raises; without
            # this the panel keeps saying Streaming over a dead apply loop
            # (2026-07-10 GUI demo finding).
            logging.getLogger("posecap_addon").exception("pose apply tick failed")
            self.stop(unregister_timer=False, bpy_module=self._bpy_module)
            self._settings.lifecycle_state = "STOPPED"
            self._settings.status_message = f"Apply failed: {exc} (see posecap-addon.log)"
            return None
        self._flag_long_start_if_stalled()
        return result

    def _flag_long_start_if_stalled(self) -> None:
        """Explain the silent first-run engine warmup without faking detection."""
        if self._settings.lifecycle_state != "STARTING":
            return
        if _now() - self._started_at < _LONG_START_SECONDS:
            return
        if self._settings.status_message == _LONG_START_MESSAGE:
            return
        self._settings.status_message = _LONG_START_MESSAGE
        tag_view3d_redraw(self._bpy_module.context)

    def stop(self, *, unregister_timer: bool, bpy_module: Any) -> None:
        if self._stopped:
            return
        self._stopped = True
        # Every teardown path (normal and abnormal) ends any active recording,
        # so no later stream can inherit the flag. Playback pause stays on the
        # operator-context stop paths, where the screen context is valid.
        self._settings.record_live_mocap = False
        if unregister_timer:
            _unregister_timer(bpy_module, self.timer_callback)
        self._timer.stop()
        self._engine.stop(timeout_seconds=5.0)


def _stream_error_status(lifecycle_state: str, error: object) -> str:
    """A connect failure and a mid-stream drop read differently to the user."""
    if lifecycle_state == "STARTING":
        return f"Connect failed: {error}"
    return f"Stream stopped: {error}"


def _unregister_timer(bpy_module: Any, callback: Callable[[], float | None]) -> None:
    timers = bpy_module.app.timers
    is_registered = getattr(timers, "is_registered", None)
    if callable(is_registered) and not bool(is_registered(callback)):
        return
    with suppress(ValueError):
        timers.unregister(callback)
