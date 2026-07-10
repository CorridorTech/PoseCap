import json
import re
import socket
import time
from io import StringIO
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from posecap_contracts import SCHEMA_VERSION, PoseFrame, decode_pose_frame
from posecap_engine import PEAR_MODELS_REVISION, PEAR_REVISION
from posecap_engine.capture import CameraDevice
from posecap_engine.cli import run
from posecap_engine.errors import CaptureUnavailableError


def test_devices_command_prints_json_for_addon_dropdown(monkeypatch) -> None:
    monkeypatch.setattr(
        "posecap_engine.capture.enumerate_devices",
        lambda max_index: [
            CameraDevice(index=max_index, name="Camera X", width=None, height=None, fps=None)
        ],
    )
    stdout = StringIO()
    stderr = StringIO()

    code = run(["devices", "--max-index", "3"], stdout=stdout, stderr=stderr)

    assert code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == {
        "devices": [{"index": 3, "name": "Camera X", "width": None, "height": None, "fps": None}]
    }


def test_devices_command_reports_unavailable_capture_as_empty_list(monkeypatch) -> None:
    def unavailable(max_index: int) -> list[CameraDevice]:
        raise CaptureUnavailableError(f"no capture backend up to {max_index}")

    monkeypatch.setattr("posecap_engine.capture.enumerate_devices", unavailable)
    stdout = StringIO()
    stderr = StringIO()

    code = run(["devices", "--max-index", "1"], stdout=stdout, stderr=stderr)

    assert code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == {
        "devices": [],
        "error": "no capture backend up to 1",
    }


def test_live_command_requires_fixture_or_pear_root() -> None:
    stdout = StringIO()
    stderr = StringIO()

    code = run(["live"], stdout=stdout, stderr=stderr)

    assert code == 1
    assert "live requires either --fixture or --pear-root" in stderr.getvalue()


def test_live_command_passes_pear_options_to_frame_source(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePearFrameSource:
        def __init__(
            self,
            pear_root: Path,
            *,
            source: int | str,
            width: int,
            height: int,
            yolo_threshold: float,
            crop_ratio: float,
        ) -> None:
            captured["source"] = {
                "pear_root": pear_root,
                "source": source,
                "width": width,
                "height": height,
                "yolo_threshold": yolo_threshold,
                "crop_ratio": crop_ratio,
            }

        def frames(self):
            return iter(())

    monkeypatch.setattr("posecap_engine.cli.PearFrameSource", FakePearFrameSource)
    monkeypatch.setattr("posecap_engine.cli.serve_once", lambda frames, **kwargs: None)
    stdout = StringIO()
    stderr = StringIO()

    code = run(
        [
            "live",
            "--pear-root",
            "C:/PEAR",
            "--camera-index",
            "4",
            "--width",
            "640",
            "--height",
            "480",
            "--yolo-threshold",
            "0.45",
            "--crop-ratio",
            "1.5",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 0
    assert stderr.getvalue() == ""
    assert captured["source"] == {
        "pear_root": Path("C:/PEAR"),
        "source": 4,
        "width": 640,
        "height": 480,
        "yolo_threshold": 0.45,
        "crop_ratio": 1.5,
    }


def test_live_command_source_accepts_video_file_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePearFrameSource:
        def __init__(self, pear_root: Path, *, source: int | str, **_kwargs: object) -> None:
            captured["source"] = source

        def frames(self):
            return iter(())

    monkeypatch.setattr("posecap_engine.cli.PearFrameSource", FakePearFrameSource)
    monkeypatch.setattr("posecap_engine.cli.serve_once", lambda frames, **kwargs: None)

    code = run(
        ["live", "--pear-root", "C:/PEAR", "--source", "assets/dance.mp4"],
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert code == 0
    assert captured["source"] == "assets/dance.mp4"


def test_live_command_source_digits_parse_as_camera_index(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePearFrameSource:
        def __init__(self, pear_root: Path, *, source: int | str, **_kwargs: object) -> None:
            captured["source"] = source

        def frames(self):
            return iter(())

    monkeypatch.setattr("posecap_engine.cli.PearFrameSource", FakePearFrameSource)
    monkeypatch.setattr("posecap_engine.cli.serve_once", lambda frames, **kwargs: None)

    code = run(
        ["live", "--pear-root", "C:/PEAR", "--source", "3", "--camera-index", "7"],
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert code == 0
    assert captured["source"] == 3


def test_live_command_source_negative_index_keeps_camera_semantics(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakePearFrameSource:
        def __init__(self, pear_root: Path, *, source: int | str, **_kwargs: object) -> None:
            captured["source"] = source

        def frames(self):
            return iter(())

    monkeypatch.setattr("posecap_engine.cli.PearFrameSource", FakePearFrameSource)
    monkeypatch.setattr("posecap_engine.cli.serve_once", lambda frames, **kwargs: None)

    code = run(
        ["live", "--pear-root", "C:/PEAR", "--source", "-1"],
        stdout=StringIO(),
        stderr=StringIO(),
    )

    assert code == 0
    assert captured["source"] == -1


def test_live_command_serves_no_person_frame_from_pear_source(monkeypatch, tmp_path: Path) -> None:
    class FakePearFrameSource:
        def __init__(self, pear_root: Path, **_kwargs: object) -> None:
            self._pear_root = pear_root

        def frames(self):
            assert self._pear_root == tmp_path / "pear"
            yield PoseFrame(SCHEMA_VERSION, 0, 123.5, "no_person", None)

    monkeypatch.setattr("posecap_engine.cli.PearFrameSource", FakePearFrameSource)
    stdout = _ThreadedStdout()
    stderr = StringIO()
    code: Queue[int] = Queue()
    thread = Thread(
        target=lambda: code.put(
            run(
                [
                    "live",
                    "--pear-root",
                    str(tmp_path / "pear"),
                    "--port",
                    "0",
                ],
                stdout=stdout,
                stderr=stderr,
            )
        ),
        daemon=True,
    )
    thread.start()

    listening = json.loads(stdout.next_line(timeout=2))
    with socket.create_connection((listening["host"], listening["port"]), timeout=2) as client:
        reader = client.makefile("r", encoding="utf-8")
        frame = decode_pose_frame(reader.readline())
        assert reader.readline() == ""

    thread.join(timeout=2)
    if thread.is_alive():
        raise AssertionError("live command did not exit after serving the frame")
    assert code.get(timeout=0) == 0
    assert stderr.getvalue() == ""
    assert (frame.seq, frame.status, frame.pose) == (0, "no_person", None)


def test_doctor_command_prints_json_and_returns_error_code(monkeypatch) -> None:
    monkeypatch.setattr(
        "posecap_engine.cli.run_doctor",
        lambda **_kwargs: {
            "ok": False,
            "pear_root": None,
            "checks": [
                {"name": "torch_cuda", "status": "error", "message": "missing", "details": {}}
            ],
        },
    )
    stdout = StringIO()
    stderr = StringIO()

    code = run(["doctor"], stdout=stdout, stderr=stderr)

    assert code == 1
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue()) == {
        "ok": False,
        "pear_root": None,
        "checks": [{"name": "torch_cuda", "status": "error", "message": "missing", "details": {}}],
    }


def test_external_pear_pins_are_full_commit_shas() -> None:
    assert re.fullmatch(r"[0-9a-f]{40}", PEAR_REVISION)
    assert re.fullmatch(r"[0-9a-f]{40}", PEAR_MODELS_REVISION)


class _ThreadedStdout(StringIO):
    def __init__(self) -> None:
        super().__init__()
        self._lines: Queue[str] = Queue()
        self._buffer = ""

    def write(self, text: str) -> int:
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._lines.put(line)
        return len(text)

    def flush(self) -> None:
        return None

    def next_line(self, *, timeout: float) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                return self._lines.get(timeout=0.01)
            except Empty:
                continue
        raise AssertionError("timed out waiting for stdout line")
