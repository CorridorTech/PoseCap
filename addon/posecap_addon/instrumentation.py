"""Bounded logging helpers for addon runtime instrumentation."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Protocol

Clock = Callable[[], float]

_HANDLER_MARKER = "_posecap_addon_log_path"


class InfoLogger(Protocol):
    def info(self, __message: str, *args: object) -> None: ...


class ApplyTimeInstrumentation:
    """Aggregate pose apply timings and emit INFO logs on a fixed interval."""

    def __init__(
        self,
        *,
        logger: InfoLogger,
        clock: Clock = time.perf_counter,
        interval_seconds: float = 5.0,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self._logger = logger
        self._clock = clock
        self._interval_seconds = interval_seconds
        self._next_report_at = self._clock() + interval_seconds
        self._sample_count = 0
        self._total_seconds = 0.0
        self._max_seconds = 0.0

    def record(self, duration_seconds: float) -> None:
        """Record one applied-frame duration and log aggregate timing on interval."""
        self._record(duration_seconds, self._clock())

    def mark_start(self) -> float:
        """Return a timestamp that can be passed to record_since."""
        return self._clock()

    def record_since(self, started_at: float) -> None:
        """Record one duration measured from a previous mark_start timestamp."""
        now = self._clock()
        self._record(now - started_at, now)

    def _record(self, duration_seconds: float, now: float) -> None:
        self._sample_count += 1
        self._total_seconds += duration_seconds
        self._max_seconds = max(self._max_seconds, duration_seconds)
        if now < self._next_report_at:
            return
        average_ms = (self._total_seconds / self._sample_count) * 1000.0
        max_ms = self._max_seconds * 1000.0
        self._logger.info(
            "pose_apply_time frames=%d avg_ms=%.3f max_ms=%.3f",
            self._sample_count,
            average_ms,
            max_ms,
        )
        self._sample_count = 0
        self._total_seconds = 0.0
        self._max_seconds = 0.0
        self._next_report_at = now + self._interval_seconds


def configure_addon_logging(
    log_path: Path,
    *,
    logger: logging.Logger | None = None,
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure a bounded rotating addon log file and return its logger."""
    resolved_path = Path(log_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    configured_logger = logger or logging.getLogger("posecap_addon")
    configured_logger.setLevel(logging.INFO)
    if _has_posecap_handler(configured_logger, resolved_path):
        return configured_logger
    handler = RotatingFileHandler(
        resolved_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    setattr(handler, _HANDLER_MARKER, str(resolved_path))
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    configured_logger.addHandler(handler)
    return configured_logger


def _has_posecap_handler(logger: logging.Logger, log_path: Path) -> bool:
    expected = str(log_path)
    return any(getattr(handler, _HANDLER_MARKER, None) == expected for handler in logger.handlers)
