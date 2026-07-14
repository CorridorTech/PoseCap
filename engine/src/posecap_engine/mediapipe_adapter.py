"""MediaPipe Pose Backend adapter for the PoseCap TCP rotation contract."""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable, Generator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from posecap_contracts import SCHEMA_VERSION, PoseFrame
from posecap_core import LandmarkMap, LandmarkPoseConverter

from .errors import CaptureUnavailableError, EngineError
from .live_source import CameraSource, LiveSource

_CAMERA_READ_RETRY_SECONDS = 0.005
_DEFAULT_MAX_CAMERA_READ_FAILURES = 200


@dataclass(frozen=True)
class MediaPipeLiveConfig:
    """Runtime settings owned by the isolated MediaPipe backend."""

    model_path: Path
    source: LiveSource
    width: int = 1280
    height: int = 720
    source_loop: bool = False


class _MediaPipeRuntime(Protocol):
    def infer(self, rgb_image: object) -> LandmarkMap | None: ...

    def close(self) -> None: ...


class _LiveCapture(Protocol):
    exhausted: bool

    def read_rgb(self) -> object | None: ...

    def release(self) -> None: ...


class _PreviewWriter(Protocol):
    def offer(self, rgb_image: object) -> None: ...

    def close(self) -> None: ...


RuntimeFactory = Callable[[MediaPipeLiveConfig], _MediaPipeRuntime]
CaptureFactory = Callable[[MediaPipeLiveConfig], _LiveCapture]
Clock = Callable[[], float]


class MediaPipeFrameSource:
    """Turn MediaPipe body landmarks into schema-valid live pose frames."""

    def __init__(
        self,
        model_path: Path,
        *,
        source: LiveSource,
        width: int = 1280,
        height: int = 720,
        source_loop: bool = False,
        runtime_factory: RuntimeFactory | None = None,
        capture_factory: CaptureFactory | None = None,
        clock: Clock = time.time,
        max_camera_read_failures: int = _DEFAULT_MAX_CAMERA_READ_FAILURES,
        preview_writer: _PreviewWriter | None = None,
    ) -> None:
        if max_camera_read_failures <= 0:
            raise ValueError("max_camera_read_failures must be positive")
        self._config = MediaPipeLiveConfig(
            model_path=model_path,
            source=source,
            width=width,
            height=height,
            source_loop=source_loop,
        )
        self._runtime_factory = runtime_factory or _load_runtime
        self._capture_factory = capture_factory or _open_capture
        self._clock = clock
        self._max_camera_read_failures = max_camera_read_failures
        self._preview_writer = preview_writer

    def frames(self) -> Generator[PoseFrame, None, None]:
        runtime = self._runtime_factory(self._config)
        capture = self._capture_factory(self._config)
        converter = LandmarkPoseConverter()
        seq = 0
        failed_reads = 0
        try:
            while True:
                rgb_image = capture.read_rgb()
                if rgb_image is None:
                    if capture.exhausted:
                        return
                    failed_reads += 1
                    if failed_reads >= self._max_camera_read_failures:
                        raise CaptureUnavailableError(
                            f"{_describe_source(self._config.source)} did not return frames "
                            f"after {failed_reads} consecutive reads"
                        )
                    time.sleep(_CAMERA_READ_RETRY_SECONDS)
                    continue
                failed_reads = 0
                if self._preview_writer is not None:
                    self._preview_writer.offer(rgb_image)
                captured_at = self._clock()
                landmarks = runtime.infer(rgb_image)
                if landmarks is None:
                    yield PoseFrame(SCHEMA_VERSION, seq, captured_at, "no_person", None)
                else:
                    yield PoseFrame(
                        SCHEMA_VERSION,
                        seq,
                        captured_at,
                        "ok",
                        converter.convert(landmarks),
                    )
                seq += 1
        finally:
            capture.release()
            if self._preview_writer is not None:
                with suppress(Exception):
                    self._preview_writer.close()
            with suppress(Exception):
                runtime.close()


_LANDMARK_INDICES = {
    "nose": 0,
    "left_ear": 7,
    "right_ear": 8,
    "mouth_left": 9,
    "mouth_right": 10,
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_elbow": 13,
    "right_elbow": 14,
    "left_wrist": 15,
    "right_wrist": 16,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
    "left_heel": 29,
    "right_heel": 30,
    "left_foot_index": 31,
    "right_foot_index": 32,
}


class _MediaPipeTaskRuntime:
    def __init__(self, config: MediaPipeLiveConfig, mediapipe: Any) -> None:
        if not config.model_path.is_file():
            raise EngineError(f"MediaPipe model was not found: {config.model_path}")
        self._mediapipe = mediapipe
        options = mediapipe.tasks.vision.HolisticLandmarkerOptions(
            base_options=mediapipe.tasks.BaseOptions(
                model_asset_path=str(config.model_path),
                delegate=mediapipe.tasks.BaseOptions.Delegate.CPU,
            ),
            running_mode=mediapipe.tasks.vision.RunningMode.VIDEO,
        )
        self._landmarker = mediapipe.tasks.vision.HolisticLandmarker.create_from_options(options)
        self._timestamp_ms = -1

    def infer(self, rgb_image: object) -> LandmarkMap | None:
        image = np.asarray(rgb_image, dtype=np.uint8)
        media_image = self._mediapipe.Image(
            image_format=self._mediapipe.ImageFormat.SRGB,
            data=image,
        )
        self._timestamp_ms = max(self._timestamp_ms + 1, int(time.monotonic() * 1_000))
        result = self._landmarker.detect_for_video(media_image, self._timestamp_ms)
        landmarks = result.pose_world_landmarks
        if len(landmarks) < 33:
            return None
        return {
            name: (
                float(landmarks[index].x),
                -float(landmarks[index].y),
                -float(landmarks[index].z),
            )
            for name, index in _LANDMARK_INDICES.items()
        }

    def close(self) -> None:
        self._landmarker.close()


def _load_runtime(config: MediaPipeLiveConfig) -> _MediaPipeRuntime:
    try:
        mediapipe = importlib.import_module("mediapipe")
    except ImportError as error:
        raise EngineError("MediaPipe is not installed in this Pose Backend runtime") from error
    return _MediaPipeTaskRuntime(config, mediapipe)


class _OpenCvCapture:
    def __init__(self, config: MediaPipeLiveConfig, cv2: Any) -> None:
        self._cv2 = cv2
        self._loop = config.source_loop
        if isinstance(config.source, CameraSource):
            self._camera = True
            source: int | str = config.source.index
        else:
            self._camera = False
            source = config.source.path
        self._capture = cv2.VideoCapture(source)
        self.exhausted = False
        if not bool(self._capture.isOpened()):
            self._capture.release()
            description = f"camera index {source}" if self._camera else f"video file {source}"
            raise CaptureUnavailableError(f"could not open {description}")
        if self._camera:
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.height)

    def read_rgb(self) -> object | None:
        ok, frame = self._capture.read()
        if not bool(ok) and not self._camera and self._loop:
            self._capture.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._capture.read()
        if not bool(ok):
            if not self._camera:
                self.exhausted = True
            return None
        return self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

    def release(self) -> None:
        self._capture.release()


def _open_capture(config: MediaPipeLiveConfig) -> _LiveCapture:
    try:
        cv2 = importlib.import_module("cv2")
    except ImportError as error:
        raise EngineError("OpenCV is not installed in this Pose Backend runtime") from error
    return _OpenCvCapture(config, cv2)


def _describe_source(source: LiveSource) -> str:
    if isinstance(source, CameraSource):
        return f"camera index {source.index}"
    return f"video file {source.path}"
