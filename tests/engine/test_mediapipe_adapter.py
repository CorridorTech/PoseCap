import itertools
import json
import math
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from posecap_contracts import decode_pose_frame
from posecap_core import LandmarkMap
from posecap_engine.mediapipe_adapter import MediaPipeFrameSource
from posecap_engine.pear_adapter import CameraSource, VideoFileSource


def test_mediapipe_source_emits_posecap_body_frame_then_no_person() -> None:
    capture = _FakeCapture([object(), object()])
    runtime = _FakeRuntime([_neutral_landmarks(), None])
    source = MediaPipeFrameSource(
        Path("holistic_landmarker.task"),
        source=CameraSource(0),
        runtime_factory=lambda _config: runtime,
        capture_factory=lambda _config: capture,
        clock=iter([10.0, 11.0]).__next__,
    )

    frames = list(source.frames())

    assert [(frame.seq, frame.captured_at, frame.status) for frame in frames] == [
        (0, 10.0, "ok"),
        (1, 11.0, "no_person"),
    ]
    assert frames[0].pose is not None
    assert capture.released


def test_mediapipe_source_previews_each_captured_frame_and_closes_window() -> None:
    first_frame = object()
    second_frame = object()
    capture = _FakeCapture([first_frame, second_frame])
    preview = _FakePreview()
    source = MediaPipeFrameSource(
        Path("holistic_landmarker.task"),
        source=CameraSource(0),
        runtime_factory=lambda _config: _FakeRuntime([_neutral_landmarks(), None]),
        capture_factory=lambda _config: capture,
        preview_writer=preview,
    )

    list(source.frames())

    assert preview.offered == [first_frame, second_frame]
    assert preview.closed


def test_mediapipe_adapter_imports_without_loading_the_pear_adapter() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import posecap_engine.mediapipe_adapter; "
            "assert 'posecap_engine.pear_adapter' not in sys.modules",
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.integration
@pytest.mark.slow
def test_real_mediapipe_video_emits_finite_posecap_frames() -> None:
    configured_model = os.environ.get("POSECAP_MEDIAPIPE_MODEL")
    if configured_model is None:
        pytest.skip("set POSECAP_MEDIAPIPE_MODEL to run the real MediaPipe backend")
    source = MediaPipeFrameSource(
        Path(configured_model),
        source=VideoFileSource("tests/fixtures/video/ale_t_pose_1280x720_30fps.mp4"),
    )

    frames = list(itertools.islice(source.frames(), 8))

    assert len(frames) == 8
    assert any(frame.status == "ok" for frame in frames)
    for frame in frames:
        if frame.pose is None:
            continue
        values = [
            *frame.pose.global_orient,
            *(value for row in frame.pose.body_pose for value in row),
        ]
        assert all(math.isfinite(value) for value in values)


@pytest.mark.integration
@pytest.mark.slow
def test_real_mediapipe_cli_streams_video_over_tcp() -> None:
    configured_model = os.environ.get("POSECAP_MEDIAPIPE_MODEL")
    if configured_model is None:
        pytest.skip("set POSECAP_MEDIAPIPE_MODEL to run the real MediaPipe backend")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "posecap_engine.mediapipe_cli",
            "live",
            "--model-path",
            configured_model,
            "--source",
            "tests/fixtures/video/ale_t_pose_1280x720_30fps.mp4",
            "--port",
            "0",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        listening = json.loads(process.stdout.readline())
        with (
            socket.create_connection((listening["host"], listening["port"]), timeout=30) as client,
            client.makefile("r", encoding="utf-8") as reader,
        ):
            frames = [decode_pose_frame(reader.readline()) for _ in range(8)]
        assert len(frames) == 8
        assert any(frame.status == "ok" for frame in frames)
        assert process.wait(timeout=30) == 0
    finally:
        if process.poll() is None:
            process.kill()


class _FakeCapture:
    def __init__(self, frames: list[object]) -> None:
        self._frames = iter(frames)
        self.exhausted = False
        self.released = False

    def read_rgb(self) -> object | None:
        try:
            return next(self._frames)
        except StopIteration:
            self.exhausted = True
            return None

    def release(self) -> None:
        self.released = True


class _FakeRuntime:
    def __init__(self, results: list[LandmarkMap | None]) -> None:
        self._results = iter(results)

    def infer(self, rgb_image: object) -> LandmarkMap | None:
        del rgb_image
        return next(self._results)

    def close(self) -> None:
        pass


class _FakePreview:
    def __init__(self) -> None:
        self.offered: list[object] = []
        self.closed = False

    def offer(self, rgb_image: object) -> None:
        self.offered.append(rgb_image)

    def close(self) -> None:
        self.closed = True


def _neutral_landmarks() -> dict[str, tuple[float, float, float]]:
    return {
        "left_hip": (0.2, 0.0, 0.0),
        "right_hip": (-0.2, 0.0, 0.0),
        "left_shoulder": (0.4, 1.0, 0.0),
        "right_shoulder": (-0.4, 1.0, 0.0),
        "left_elbow": (0.7, 1.0, 0.0),
        "right_elbow": (-0.7, 1.0, 0.0),
        "left_wrist": (1.0, 1.0, 0.0),
        "right_wrist": (-1.0, 1.0, 0.0),
        "left_knee": (0.2, -1.0, 0.0),
        "right_knee": (-0.2, -1.0, 0.0),
        "left_ankle": (0.2, -2.0, 0.0),
        "right_ankle": (-0.2, -2.0, 0.0),
        "left_heel": (0.2, -2.0, -0.1),
        "right_heel": (-0.2, -2.0, -0.1),
        "left_foot_index": (0.2, -2.0, 0.3),
        "right_foot_index": (-0.2, -2.0, 0.3),
        "left_ear": (0.1, 1.55, 0.0),
        "right_ear": (-0.1, 1.55, 0.0),
        "mouth_left": (0.04, 1.4, 0.0),
        "mouth_right": (-0.04, 1.4, 0.0),
        "nose": (0.0, 1.5, 0.0),
    }
