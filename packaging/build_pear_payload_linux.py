"""Build the external PEAR bootstrap payload for Linux.

Mirrors packaging/build_pear_payload.ps1's steps -- stage the uv binary,
build the three PoseCap wheels, repack an already-installed PyTorch3D into a
wheel (tools/repack_wheel.py, already platform-neutral -- it reads the wheel
tag from the installed distribution's own metadata), copy the locks, verify
the pinned PEAR source revision, then hand off to the shared
tools/build_pear_payload.py packer -- but staging a POSIX `bin/uv` (no .exe)
and packaging/requirements-pypi-linux.lock instead of the Windows lock file.
requirements-torch.lock needs no Linux variant: it's already platform-neutral
and already validated identical on Linux.

PyTorch3D has no route into this script that builds it from source or
downloads a third-party wheel -- run
    uv pip install --python <venv>/bin/python torch==2.9.1+cu128 torchvision==0.24.1+cu128 \\
      --index-url https://download.pytorch.org/whl/cu128
    uv pip install --python <venv>/bin/python \\
      --extra-index-url https://miropsota.github.io/torch_packages_builder \\
      "pytorch3d==0.7.9+d9839a9pt2.9.1cu128"
first (or build PyTorch3D from source), then point --pytorch3d-site-packages
at that venv's site-packages -- the same shape the Windows script requires.

    uv run python packaging/build_pear_payload_linux.py \\
      --pytorch3d-site-packages /path/to/venv/lib/python3.11/site-packages \\
      --base-url https://github.com/CorridorTech/PoseCap/releases/download/<tag>
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PACKAGING_DIR = Path(__file__).resolve().parent
_WORKSPACE_PACKAGES = ("posecap-contracts", "posecap-core", "posecap-engine")

Runner = Callable[[Sequence[str]], None]


class PearPayloadBuildError(RuntimeError):
    """Raised when the Linux PEAR payload cannot be built."""


def build_pear_payload_for_linux(
    *,
    pytorch3d_site_packages: Path,
    base_url: str,
    build_number: int = 1,
    output_dir: Path | None = None,
    staging_dir: Path | None = None,
    runner: Runner | None = None,
    uv_path: Path | None = None,
) -> Path:
    """Stage and package the Linux PEAR bootstrap; return the output dir."""
    run = runner or _run_checked
    output_dir = (output_dir or _PACKAGING_DIR / "dist").resolve()
    staging = (staging_dir or _PACKAGING_DIR / "work" / "pear-payload-staging-linux").resolve()
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "bin").mkdir(parents=True)
    (staging / "wheels").mkdir(parents=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    version_label = f"{_workspace_version()}-linux.{build_number}"
    pear_revision = _pear_revision()
    source_lock = _pear_source_lock()
    if source_lock["revision"] != pear_revision:
        raise PearPayloadBuildError(
            f"PEAR source lock revision {source_lock['revision']!r} does not match "
            f"engine config {pear_revision!r}"
        )

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

    resolved_site_packages = pytorch3d_site_packages.resolve()
    if not (resolved_site_packages / "pytorch3d").is_dir():
        raise PearPayloadBuildError(f"pytorch3d package not found in {resolved_site_packages}")
    run(
        [
            str(uv),
            "run",
            "python",
            str(_REPO_ROOT / "tools" / "repack_wheel.py"),
            "--site-packages",
            str(resolved_site_packages),
            "--distribution",
            "pytorch3d",
            "--output-dir",
            str(staging / "wheels"),
        ]
    )
    stray_gitignore = staging / "wheels" / ".gitignore"
    stray_gitignore.unlink(missing_ok=True)

    shutil.copyfile(_PACKAGING_DIR / "requirements-torch.lock", staging / "requirements-torch.lock")
    shutil.copyfile(
        _PACKAGING_DIR / "requirements-pypi-linux.lock", staging / "requirements-pypi.lock"
    )

    run(
        [
            str(uv),
            "run",
            "python",
            str(_REPO_ROOT / "tools" / "build_pear_payload.py"),
            "--source",
            str(staging),
            "--version",
            version_label,
            "--base-url",
            base_url,
            "--pear-source-url",
            str(source_lock["url"]),
            "--pear-source-sha256",
            str(source_lock["sha256"]),
            "--pear-source-size",
            str(source_lock["size_bytes"]),
            "--output-dir",
            str(output_dir),
        ]
    )
    return output_dir


def _workspace_version() -> str:
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'version = "([^"]+)"', pyproject)
    if match is None:
        raise PearPayloadBuildError("version not found in pyproject.toml")
    return match.group(1)


def _pear_revision() -> str:
    config_py = (_REPO_ROOT / "engine" / "src" / "posecap_engine" / "config.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'PEAR_REVISION = "([0-9a-f]{40})"', config_py)
    if match is None:
        raise PearPayloadBuildError("PEAR_REVISION not found in engine config")
    return match.group(1)


def _pear_source_lock() -> dict[str, object]:
    lock_path = _PACKAGING_DIR / "pear-source.lock.json"
    return json.loads(lock_path.read_text(encoding="utf-8"))


def _find_uv() -> Path:
    found = shutil.which("uv")
    if found is None:
        raise PearPayloadBuildError("uv not found on PATH")
    return Path(found)


def _run_checked(command: Sequence[str]) -> None:
    result = subprocess.run(list(command), check=False)
    if result.returncode != 0:
        raise PearPayloadBuildError(
            f"{command[0]} exited with code {result.returncode}: {' '.join(command)}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pytorch3d-site-packages", type=Path, required=True)
    parser.add_argument("--build-number", type=int, default=1)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        output_dir = build_pear_payload_for_linux(
            pytorch3d_site_packages=args.pytorch3d_site_packages,
            base_url=args.base_url,
            build_number=args.build_number,
            output_dir=args.output_dir,
        )
    except (OSError, PearPayloadBuildError) as error:
        print(f"could not build the Linux PEAR payload: {error}", file=sys.stderr)
        return 2
    print(f"==> payload directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
