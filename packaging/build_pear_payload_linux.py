"""Build the external PEAR bootstrap payload for Linux.

Mirrors packaging/build_pear_payload.ps1's steps -- stage the uv binary,
build the three PoseCap wheels, get a PyTorch3D wheel into the payload, copy
the locks, verify the pinned PEAR source revision, then hand off to the
shared tools/build_pear_payload.py packer -- but staging a POSIX `bin/uv`
(no .exe) and packaging/requirements-pypi-linux.lock instead of the Windows
lock file. requirements-torch.lock needs no Linux variant: it's already
platform-neutral and already validated identical on Linux.

Normal path -- a wheel Corridor's own pinned build already produced:
    uv run python packaging/build_pear_payload_linux.py \\
      --pytorch3d-wheel /path/to/pytorch3d-0.7.9-cp311-cp311-linux_x86_64.whl \\
      --base-url https://github.com/CorridorTech/PoseCap/releases/download/<tag>
This mirrors the Windows shape (build_pear_payload.ps1's "repack pytorch3d
wheel" step): PyTorch3D is compiled once, in a pinned environment we control
(a manylinux-style CUDA 12.8 container -- see the PR #98 review thread), not
on the machine running this script.

Fallback path -- no wheel available yet, build one locally from source
against a host CUDA Toolkit (needs a matching CUDA/host-GCC/glibc
toolchain -- see doc/guides/linux-install.md's manual PEAR steps, and
packaging/install_linux.py's --build-pytorch3d-from-source flag which drives
this for the one-command path via _build_pytorch3d_venv, mirroring
tools/install/setup_pear_runtime.ps1):
    uv pip install --python <venv>/bin/python torch==2.9.1+cu128 torchvision==0.24.1+cu128 \\
      --index-url https://download.pytorch.org/whl/cu128
    git clone --branch v0.7.9 --depth 1 https://github.com/facebookresearch/pytorch3d.git p3d
    CUDA_HOME=/usr/local/cuda-12.8 CUB_HOME=/usr/local/cuda-12.8/include MAX_JOBS=1 \\
      uv pip install --python <venv>/bin/python p3d --no-build-isolation
then point --pytorch3d-site-packages at that venv's site-packages; this
script repacks it into a wheel itself (tools/repack_wheel.py, already
platform-neutral -- it reads the wheel tag from the installed distribution's
own metadata).

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
    base_url: str,
    pytorch3d_site_packages: Path | None = None,
    pytorch3d_wheel: Path | None = None,
    build_number: int = 1,
    output_dir: Path | None = None,
    staging_dir: Path | None = None,
    runner: Runner | None = None,
    uv_path: Path | None = None,
) -> Path:
    """Stage and package the Linux PEAR bootstrap; return the output dir.

    Exactly one of pytorch3d_wheel (the normal path -- a wheel already built
    in a pinned environment) or pytorch3d_site_packages (the from-source
    fallback -- repack an installed distribution) must be given.
    """
    if (pytorch3d_wheel is None) == (pytorch3d_site_packages is None):
        raise PearPayloadBuildError(
            "exactly one of pytorch3d_wheel or pytorch3d_site_packages must be given"
        )
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

    if pytorch3d_wheel is not None:
        resolved_wheel = pytorch3d_wheel.resolve()
        if not resolved_wheel.is_file():
            raise PearPayloadBuildError(f"pytorch3d wheel not found at {resolved_wheel}")
        shutil.copyfile(resolved_wheel, staging / "wheels" / resolved_wheel.name)
    else:
        assert pytorch3d_site_packages is not None  # guaranteed by the exclusivity check above
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--pytorch3d-wheel", type=Path, help="prebuilt wheel -- the normal path (see module doc)"
    )
    group.add_argument(
        "--pytorch3d-site-packages",
        type=Path,
        help="installed distribution to repack -- the from-source fallback (see module doc)",
    )
    parser.add_argument("--build-number", type=int, default=1)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        output_dir = build_pear_payload_for_linux(
            pytorch3d_wheel=args.pytorch3d_wheel,
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
