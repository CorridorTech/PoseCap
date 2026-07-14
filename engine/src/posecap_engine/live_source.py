"""Neutral camera and video-source value objects shared by Pose Backends."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraSource:
    """A live webcam selected by its OpenCV device index."""

    index: int


@dataclass(frozen=True)
class VideoFileSource:
    """A finite video file; the backend decides whether its EOF loops."""

    path: str


LiveSource = CameraSource | VideoFileSource
