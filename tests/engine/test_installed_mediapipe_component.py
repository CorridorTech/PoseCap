"""Optional black-box acceptance for an installed MediaPipe component tree."""

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.slow
def test_installed_mediapipe_component_streams_fixture_video() -> None:
    root_value = os.environ.get("POSECAP_MEDIAPIPE_COMPONENT_ROOT")
    if root_value is None:
        pytest.skip("set POSECAP_MEDIAPIPE_COMPONENT_ROOT to run installed-component acceptance")
    root = Path(root_value)
    launcher = root / "backends" / "mediapipe" / "runtime" / "Scripts" / "posecap-mediapipe.exe"
    model = root / "backends" / "mediapipe" / "models" / "holistic_landmarker.task"
    video = Path(__file__).parents[1] / "fixtures" / "video" / "ale_t_pose_1280x720_30fps.mp4"
    process = subprocess.Popen(
        [
            str(launcher),
            "live",
            "--model-path",
            str(model),
            "--source",
            str(video),
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
            frames = [json.loads(reader.readline()) for _ in range(8)]
        assert process.wait(timeout=30) == 0
        assert any(frame["status"] == "ok" for frame in frames)
        assert all(frame["schema_version"] == 1 for frame in frames)
    finally:
        if process.poll() is None:
            process.kill()
