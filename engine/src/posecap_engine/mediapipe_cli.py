"""CLI for the isolated, CPU-first MediaPipe Pose Backend."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import TextIO

from .config import DEFAULT_HOST, DEFAULT_PORT
from .errors import EngineError
from .live_source import CameraSource, LiveSource, VideoFileSource
from .logging_config import configure_logging
from .mediapipe_adapter import MediaPipeFrameSource, MediaPipeLiveConfig, _load_runtime
from .preview import PreviewWindow
from .stream_server import serve_once
from .watchdog import ParentWatchdog


def main(argv: list[str] | None = None) -> int:
    return run(argv, stdout=sys.stdout, stderr=sys.stderr)


def run(argv: list[str] | None = None, *, stdout: TextIO, stderr: TextIO) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return int(args.func(args, stdout))
    except (EngineError, ValueError) as error:
        print(str(error), file=stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="posecap-mediapipe")
    subparsers = parser.add_subparsers(required=True)
    live = subparsers.add_parser("live", help="serve live body pose frames over TCP")
    live.add_argument("--model-path", type=Path, required=True)
    live.add_argument("--host", default=DEFAULT_HOST)
    live.add_argument("--port", type=int, default=DEFAULT_PORT)
    live.add_argument("--camera-index", type=int, default=0)
    live.add_argument("--source")
    live.add_argument("--source-loop", action="store_true")
    live.add_argument("--width", type=int, default=1280)
    live.add_argument("--height", type=int, default=720)
    live.add_argument("--parent-pid", type=int)
    live.add_argument("--log-file", type=Path)
    live.add_argument("--preview-window", action="store_true")
    live.add_argument("--yolo-threshold", help=argparse.SUPPRESS)
    live.add_argument("--yolo-model", help=argparse.SUPPRESS)
    live.set_defaults(func=_run_live)

    doctor = subparsers.add_parser("doctor", help="check MediaPipe runtime readiness")
    doctor.add_argument("--model-path", type=Path, required=True)
    doctor.set_defaults(func=_run_doctor)
    return parser


def _run_live(args: argparse.Namespace, stdout: TextIO) -> int:
    logger = configure_logging(args.log_file)
    source = MediaPipeFrameSource(
        args.model_path,
        source=_parse_source(args.source, args.camera_index),
        width=args.width,
        height=args.height,
        source_loop=bool(args.source_loop),
        preview_writer=_build_preview_writer(args),
    )

    def ready(address: tuple[str, int]) -> None:
        message = {"event": "listening", "host": address[0], "port": address[1]}
        print(json.dumps(message), file=stdout)
        stdout.flush()

    serve_once(
        source.frames(),
        host=args.host,
        port=args.port,
        watchdog=ParentWatchdog(args.parent_pid),
        logger=logger,
        ready=ready,
    )
    return 0


def _run_doctor(args: argparse.Namespace, stdout: TextIO) -> int:
    checks: list[dict[str, str]] = []
    if not args.model_path.is_file():
        checks.append({"name": "model", "status": "error", "detail": str(args.model_path)})
    else:
        checks.append({"name": "model", "status": "ok", "detail": str(args.model_path)})
        runtime = _load_runtime(
            MediaPipeLiveConfig(model_path=args.model_path, source=CameraSource(0))
        )
        runtime.close()
        checks.append({"name": "runtime", "status": "ok", "detail": "CPU landmarker loaded"})
    ok = all(check["status"] == "ok" for check in checks)
    report = {"ok": ok, "backend": "mediapipe", "checks": checks}
    print(json.dumps(report, sort_keys=True), file=stdout)
    return 0 if ok else 1


def _parse_source(source: str | None, camera_index: int) -> LiveSource:
    if source is None:
        return CameraSource(camera_index)
    try:
        return CameraSource(int(source))
    except ValueError:
        return VideoFileSource(source)


def _build_preview_writer(args: argparse.Namespace) -> PreviewWindow | None:
    if not bool(args.preview_window):
        return None
    try:
        cv2 = importlib.import_module("cv2")
    except ImportError as error:
        raise EngineError("OpenCV is not installed in this Pose Backend runtime") from error
    return PreviewWindow(cv2)


if __name__ == "__main__":
    raise SystemExit(main())
