"""Build the external MediaPipe Lite bootstrap payload for Linux.

Mirrors packaging/build_mediapipe_payload.ps1's steps -- stage the uv binary,
build the three PoseCap wheels, copy the pinned requirements lock, then hand
off to the shared tools/build_mediapipe_payload.py packer -- but staging a
POSIX `bin/uv` (no .exe) and packaging/requirements-mediapipe-linux.lock
instead of the Windows lock file.

    uv run python packaging/build_mediapipe_payload_linux.py \\
      --base-url https://github.com/CorridorTech/PoseCap/releases/download/<tag>
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGING_DIR = Path(__file__).resolve().parent
_WORKSPACE_PACKAGES = ("posecap-contracts", "posecap-core", "posecap-engine")
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
    "holistic_landmarker/float16/1/holistic_landmarker.task"
)
_MODEL_SHA256 = "e2dab61191e2dcd0a15f943d8e3ed1dce13c82dfa597b9dd39f562975a50c3f8"
_MODEL_SIZE = 13683609

Runner = Callable[[Sequence[str]], None]


class MediaPipePayloadBuildError(RuntimeError):
    """Raised when the Linux MediaPipe payload cannot be built."""


def build_mediapipe_payload_for_linux(
    *,
    base_url: str,
    build_number: int = 1,
    output_dir: Path | None = None,
    staging_dir: Path | None = None,
    runner: Runner | None = None,
    uv_path: Path | None = None,
) -> Path:
    """Stage and package the Linux MediaPipe Lite bootstrap; return the output dir."""
    run = runner or _run_checked
    output_dir = (output_dir or _PACKAGING_DIR / "dist").resolve()
    staging = (staging_dir or _PACKAGING_DIR / "work" / "mediapipe-payload-staging-linux").resolve()
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "bin").mkdir(parents=True)
    (staging / "wheels").mkdir(parents=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    version_label = f"{_workspace_version()}-linux.{build_number}"

    uv = uv_path or _find_uv()
    shutil.copyfile(uv, staging / "bin" / "uv")
    (staging / "bin" / "uv").chmod(0o755)

    for package in _WORKSPACE_PACKAGES:
        run(
            [
                str(uv),
                "build",
                "--wheel",
                "--package",
                package,
                "--out-dir",
                str(staging / "wheels"),
            ]
        )
    stray_gitignore = staging / "wheels" / ".gitignore"
    stray_gitignore.unlink(missing_ok=True)

    shutil.copyfile(
        _PACKAGING_DIR / "requirements-mediapipe-linux.lock",
        staging / "requirements-mediapipe.lock",
    )

    run(
        [
            str(uv),
            "run",
            "python",
            str(_REPO_ROOT / "tools" / "build_mediapipe_payload.py"),
            "--source",
            str(staging),
            "--version",
            version_label,
            "--base-url",
            base_url,
            "--model-url",
            _MODEL_URL,
            "--model-sha256",
            _MODEL_SHA256,
            "--model-size",
            str(_MODEL_SIZE),
            "--output-dir",
            str(output_dir),
        ]
    )
    return output_dir


def _workspace_version() -> str:
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'version = "([^"]+)"', pyproject)
    if match is None:
        raise MediaPipePayloadBuildError("version not found in pyproject.toml")
    return match.group(1)


def _find_uv() -> Path:
    found = shutil.which("uv")
    if found is None:
        raise MediaPipePayloadBuildError("uv not found on PATH")
    return Path(found)


def _run_checked(command: Sequence[str]) -> None:
    result = subprocess.run(list(command), check=False)
    if result.returncode != 0:
        raise MediaPipePayloadBuildError(
            f"{command[0]} exited with code {result.returncode}: {' '.join(command)}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-number", type=int, default=1)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        output_dir = build_mediapipe_payload_for_linux(
            base_url=args.base_url,
            build_number=args.build_number,
            output_dir=args.output_dir,
        )
    except (OSError, MediaPipePayloadBuildError) as error:
        print(f"could not build the Linux MediaPipe payload: {error}", file=sys.stderr)
        return 2
    print(f"==> payload directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
