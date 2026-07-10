"""Command line entry point for the PoseCap engine bridge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO

from . import capture
from .config import DEFAULT_HOST, DEFAULT_PORT
from .doctor import encode_doctor_report, run_doctor
from .errors import EngineError
from .frame_sources import FixtureFrameSource
from .logging_config import configure_logging
from .pear_adapter import PearFrameSource
from .stream_server import serve_once
from .watchdog import ParentWatchdog


def main(argv: list[str] | None = None) -> int:
    return run(argv, stdout=sys.stdout, stderr=sys.stderr)


def run(
    argv: list[str] | None = None,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args, stdout))
    except EngineError as exc:
        print(str(exc), file=stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="posecap-engine")
    subparsers = parser.add_subparsers(required=True)

    devices = subparsers.add_parser("devices", help="print available webcam devices as JSON")
    devices.add_argument("--max-index", type=int, default=8)
    devices.set_defaults(func=_run_devices)

    live = subparsers.add_parser("live", help="serve live pose frames over TCP")
    live.add_argument("--host", default=DEFAULT_HOST)
    live.add_argument("--port", type=int, default=DEFAULT_PORT)
    live.add_argument("--fixture", type=Path)
    live.add_argument("--fixture-repeat", action="store_true")
    live.add_argument("--fixture-frame-interval", type=float, default=0.0)
    live.add_argument("--pear-root", type=Path)
    live.add_argument("--camera-index", type=int, default=0)
    live.add_argument(
        "--source",
        help="camera index or video file path; takes precedence over --camera-index",
    )
    live.add_argument("--width", type=int, default=1280)
    live.add_argument("--height", type=int, default=720)
    live.add_argument("--yolo-threshold", type=float, default=0.3)
    live.add_argument("--crop-ratio", type=float, default=1.75)
    live.add_argument("--parent-pid", type=int)
    live.add_argument("--log-file", type=Path)
    live.set_defaults(func=_run_live)

    doctor = subparsers.add_parser("doctor", help="check PEAR runtime readiness")
    doctor.add_argument("--pear-root", type=Path)
    doctor.add_argument("--download-weights", action="store_true")
    doctor.set_defaults(func=_run_doctor)
    return parser


def _run_devices(args: argparse.Namespace, stdout: TextIO) -> int:
    try:
        devices = [device.to_json() for device in capture.enumerate_devices(args.max_index)]
        result: dict[str, object] = {"devices": devices}
    except EngineError as exc:
        result = {"devices": [], "error": str(exc)}
    print(json.dumps(result, sort_keys=True), file=stdout)
    return 0


def _run_live(args: argparse.Namespace, stdout: TextIO) -> int:
    logger = configure_logging(args.log_file)
    source = _frame_source(args)

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
    report = run_doctor(
        pear_root=args.pear_root,
        download_weights=bool(args.download_weights),
    )
    print(encode_doctor_report(report), file=stdout)
    return 0 if bool(report["ok"]) else 1


def _frame_source(args: argparse.Namespace) -> FixtureFrameSource | PearFrameSource:
    if args.fixture is not None:
        return FixtureFrameSource(
            args.fixture,
            repeat=bool(args.fixture_repeat),
            frame_interval_seconds=float(args.fixture_frame_interval),
        )
    if args.pear_root is None:
        raise EngineError("live requires either --fixture or --pear-root")
    return PearFrameSource(
        args.pear_root,
        source=_parse_source(args.source, args.camera_index),
        width=args.width,
        height=args.height,
        yolo_threshold=args.yolo_threshold,
        crop_ratio=args.crop_ratio,
    )


def _parse_source(source: str | None, camera_index: int) -> int | str:
    if source is None:
        return camera_index
    try:
        return int(source)
    except ValueError:
        return source


if __name__ == "__main__":
    raise SystemExit(main())
