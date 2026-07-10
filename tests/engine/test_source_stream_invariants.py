"""Stream invariants for `live --source <video>` against the real PEAR runtime.

Deselected by default (gpu marker). Runs the full pipeline — fixture video in,
TCP stream out — and asserts the wire contract holds for every frame. Requires
the PEAR runtime venv and checkout; set POSECAP_PEAR_PYTHON / POSECAP_PEAR_ROOT
to override the default locations.
"""

import json
import math
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from posecap_contracts import (
    NUM_BETAS,
    NUM_BODY_JOINTS,
    NUM_EXPRESSION,
    NUM_HAND_JOINTS,
    PoseFrame,
    decode_pose_frame,
)

pytestmark = [pytest.mark.gpu, pytest.mark.integration, pytest.mark.slow]

_REPO_ROOT = Path(__file__).parents[2]
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "video"
_STREAM_TIMEOUT_SECONDS = 300

_FIXTURES = [
    ("stretch_slow_static_1280x720_25fps.mp4", 250),
    ("handstand_inversion_1280x720_25fps.mp4", 156),
    ("dance_fast_indoor_1280x720_30fps.mp4", 300),
]


@pytest.mark.parametrize(("fixture_name", "expected_frames"), _FIXTURES)
def test_source_video_stream_holds_wire_invariants(fixture_name: str, expected_frames: int) -> None:
    pear_python = _pear_python()
    pear_root = _pear_root()
    if pear_python is None:
        pytest.skip("set POSECAP_PEAR_PYTHON or create .venv-pear to run source e2e")
    if pear_root is None:
        pytest.skip("set POSECAP_PEAR_ROOT or check out PoseCap-PEAR next to the repo")

    frames, exit_code = _stream_fixture(pear_python, pear_root, _FIXTURE_DIR / fixture_name)

    assert exit_code == 0
    assert len(frames) == expected_frames
    assert [frame.seq for frame in frames] == list(range(expected_frames))
    assert {frame.status for frame in frames} <= {"ok", "no_person"}
    for frame in frames:
        if frame.pose is None:
            continue
        assert len(frame.pose.body_pose) == NUM_BODY_JOINTS
        assert len(frame.pose.left_hand_pose) == NUM_HAND_JOINTS
        assert len(frame.pose.right_hand_pose) == NUM_HAND_JOINTS
        assert len(frame.pose.betas) == NUM_BETAS
        assert len(frame.pose.expression) == NUM_EXPRESSION
        assert not _has_non_finite(frame)


def _stream_fixture(
    pear_python: Path, pear_root: Path, fixture: Path
) -> tuple[list[PoseFrame], int]:
    process = subprocess.Popen(
        [
            str(pear_python),
            "-m",
            "posecap_engine.cli",
            "live",
            "--pear-root",
            str(pear_root),
            "--source",
            str(fixture),
            "--port",
            "0",
        ],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stderr is not None
        listening = json.loads(process.stdout.readline())
        # Drain both pipes in the background: torch/lightning/ultralytics write
        # warnings to stderr, and a full pipe buffer would block the engine.
        for pipe in (process.stdout, process.stderr):
            threading.Thread(target=pipe.read, daemon=True).start()
        frames: list[PoseFrame] = []
        address = (listening["host"], listening["port"])
        with socket.create_connection(address, timeout=_STREAM_TIMEOUT_SECONDS) as client:
            client.settimeout(_STREAM_TIMEOUT_SECONDS)
            reader = client.makefile("r", encoding="utf-8")
            frames.extend(decode_pose_frame(line) for line in reader)
        return frames, process.wait(timeout=60)
    finally:
        if process.poll() is None:
            process.kill()


def _has_non_finite(frame: PoseFrame) -> bool:
    def walk(value: object) -> bool:
        if isinstance(value, list):
            return any(walk(item) for item in value)
        if isinstance(value, float):
            return math.isnan(value) or math.isinf(value)
        return False

    assert frame.pose is not None
    return any(
        walk(getattr(frame.pose, field))
        for field in (
            "global_orient",
            "body_pose",
            "left_hand_pose",
            "right_hand_pose",
            "jaw_pose",
            "betas",
            "expression",
            "transl",
        )
    )


def _pear_python() -> Path | None:
    configured = os.environ.get("POSECAP_PEAR_PYTHON")
    if configured:
        return Path(configured)
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    executable = "python.exe" if sys.platform == "win32" else "python"
    candidate = _REPO_ROOT / ".venv-pear" / scripts / executable
    if candidate.exists():
        return candidate
    return None


def _pear_root() -> Path | None:
    configured = os.environ.get("POSECAP_PEAR_ROOT")
    if configured:
        return Path(configured)
    candidate = _REPO_ROOT.parent / "PoseCap-PEAR"
    if candidate.exists():
        return candidate
    return None
