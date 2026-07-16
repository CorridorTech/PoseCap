"""Neutral camera/video-source value objects and helpers shared by Pose Backends.

Both backend adapters (MediaPipe and PEAR) read frames through the same
missed-frame policy: retry briefly, then fail with a user-facing message once
the read-failure budget is spent. That policy lives here so the two adapters
cannot drift apart (WORKFLOW section 8: two real adapters make the seam real).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .errors import CaptureUnavailableError


@dataclass(frozen=True)
class CameraSource:
    """A live webcam selected by its OpenCV device index."""

    index: int


@dataclass(frozen=True)
class VideoFileSource:
    """A finite video file; the backend decides whether its EOF loops."""

    path: str


LiveSource = CameraSource | VideoFileSource

CAMERA_READ_RETRY_SECONDS = 0.005
DEFAULT_MAX_CAMERA_READ_FAILURES = 200


def describe_source(source: LiveSource) -> str:
    """The user-facing name of a capture source, as error messages show it."""
    if isinstance(source, CameraSource):
        return f"camera index {source.index}"
    return f"video file {source.path}"


def count_failed_read(source: LiveSource, failed_reads: int, max_failures: int) -> int:
    """Count a missed frame, raising once the read-failure budget is spent.

    Sleeps ``CAMERA_READ_RETRY_SECONDS`` before returning the updated count so
    the caller's read loop does not spin hot on a stalled source.
    """
    failed_reads += 1
    if failed_reads >= max_failures:
        raise CaptureUnavailableError(
            f"{describe_source(source)} did not return frames "
            f"after {failed_reads} consecutive reads"
        )
    time.sleep(CAMERA_READ_RETRY_SECONDS)
    return failed_reads
