"""One-command Linux install: build the extension and selected Pose Backend
payload(s), stage them, and run the native installer -- all from a repo
checkout.

doc/guides/linux-install.md walks through the same pipeline as separate
steps, for when you want to see (or customize) each one; this script is that
pipeline collapsed into a single command. It is still not a downloadable
pre-built installer -- Windows users download a ready-made .exe; this builds
everything from source on your machine. Publishing pre-built Linux payload
artifacts is a release-engineering follow-up, not something a local script
can provide on its own.

    uv run python packaging/install_linux.py
    uv run python packaging/install_linux.py --components base,mediapipe
    uv run python packaging/install_linux.py --install-dir /custom/path

Components default to MediaPipe Lite always, plus PEAR too when a healthy
NVIDIA driver is detected -- the same default bootstrap_install.py itself
uses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

import build_mediapipe_payload_linux
import build_pear_payload_linux
from linux_installer import bootstrap_install, component_lifecycle
from linux_installer.nvidia_detect import nvidia_driver_present

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BASE_URL = "https://github.com/CorridorTech/PoseCap/releases/download/local-build"


class InstallLinuxError(RuntimeError):
    """Raised when the one-command Linux install cannot proceed."""


def install_linux(
    *,
    install_dir: Path,
    components: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
) -> int:
    """Run the full build-and-install pipeline; return a process exit code."""
    selected_components = components or _default_components()
    selected = component_lifecycle.parse_selected_components(selected_components)

    try:
        with tempfile.TemporaryDirectory(prefix="posecap-install-linux-") as work_dir_name:
            work_dir = Path(work_dir_name)
            _step("Build the Blender extension", lambda: _build_extension(install_dir, work_dir))
            _step(
                "Read the workspace version",
                lambda: _write_installer_manifest(install_dir, _workspace_version()),
            )
            if "mediapipe" in selected:
                _step(
                    "Build and stage the MediaPipe Lite payload",
                    lambda: _stage_mediapipe(install_dir, base_url, work_dir),
                )
            if "pear" in selected:
                _step(
                    "Build and stage the PEAR payload (this downloads ~2.5 GB of CUDA "
                    "wheels into a throwaway venv first)",
                    lambda: _stage_pear(install_dir, base_url, work_dir),
                )
    except InstallLinuxError as error:
        print(f"could not prepare the Linux install: {error}", file=sys.stderr)
        return 1

    print("\n==> Running the installer")
    return bootstrap_install.bootstrap_install(install_dir, selected_components)


def _step(label: str, action: Callable[[], None]) -> None:
    print(f"\n==> {label}")
    action()


def _default_components() -> str:
    if nvidia_driver_present():
        return "base,mediapipe,pear"
    return "base,mediapipe"


def _workspace_version() -> str:
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in pyproject.splitlines():
        if line.startswith("version = "):
            return line.split('"')[1]
    raise InstallLinuxError("version not found in pyproject.toml")


def _write_installer_manifest(install_dir: Path, version: str) -> None:
    install_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": version,
        "torchIndexUrl": "https://download.pytorch.org/whl/cu128",
        "pearRevision": build_pear_payload_linux._pear_revision(),
    }
    (install_dir / "installer_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _build_extension(install_dir: Path, work_dir: Path) -> None:
    extension_dir = work_dir / "extension"
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "tools" / "build_extension.py"),
            "--output-dir",
            str(extension_dir),
            "--release",
        ],
        check=False,
    )
    if result.returncode != 0:
        raise InstallLinuxError("building the Blender extension failed")
    zips = list(extension_dir.glob("*.zip"))
    if not zips:
        raise InstallLinuxError("extension build produced no zip file")
    destination = install_dir / "extension"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(zips[0], destination / zips[0].name)


def _stage_mediapipe(install_dir: Path, base_url: str, work_dir: Path) -> None:
    payload_output = work_dir / "mediapipe-payload"
    build_mediapipe_payload_linux.build_mediapipe_payload_for_linux(
        base_url=base_url, output_dir=payload_output
    )
    archives = list(payload_output.glob("posecap-mediapipe-bootstrap-*.zip"))
    if not archives:
        raise InstallLinuxError("MediaPipe payload build produced no archive")

    target = install_dir / "payloads" / "mediapipe"
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(target)
    uv_binary = target / "bin" / "uv"
    uv_binary.chmod(0o755)

    models_dir = install_dir / "backends" / "mediapipe" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    _download_and_verify(
        build_mediapipe_payload_linux._MODEL_URL,
        models_dir / "holistic_landmarker.task",
        build_mediapipe_payload_linux._MODEL_SHA256,
    )


def _stage_pear(install_dir: Path, base_url: str, work_dir: Path) -> None:
    venv_dir = work_dir / "pytorch3d-venv"
    _step(
        "  Create a throwaway venv with the pinned CUDA matrix (ADR-0016)",
        lambda: _build_pytorch3d_venv(venv_dir),
    )

    payload_output = work_dir / "pear-payload"
    site_packages = next((venv_dir / "lib").glob("python*/site-packages"))
    build_pear_payload_linux.build_pear_payload_for_linux(
        pytorch3d_site_packages=site_packages,
        base_url=base_url,
        output_dir=payload_output,
    )
    archives = list(payload_output.glob("posecap-pear-bootstrap-*.zip"))
    if not archives:
        raise InstallLinuxError("PEAR payload build produced no archive")

    install_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(install_dir)
    (install_dir / "bin" / "uv").chmod(0o755)

    source_lock = build_pear_payload_linux._pear_source_lock()
    pear_source_target = install_dir / "payloads" / "pear" / "pear-source.zip"
    pear_source_target.parent.mkdir(parents=True, exist_ok=True)
    _download_and_verify(str(source_lock["url"]), pear_source_target, str(source_lock["sha256"]))


def _build_pytorch3d_venv(venv_dir: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise InstallLinuxError("uv not found on PATH")
    venv_python = venv_dir / "bin" / "python"
    for args in (
        ["venv", str(venv_dir), "--python", "3.11"],
        [
            "pip",
            "install",
            "--python",
            str(venv_python),
            "torch==2.9.1+cu128",
            "torchvision==0.24.1+cu128",
            "--index-url",
            "https://download.pytorch.org/whl/cu128",
        ],
        [
            "pip",
            "install",
            "--python",
            str(venv_python),
            "--extra-index-url",
            "https://miropsota.github.io/torch_packages_builder",
            "pytorch3d==0.7.9+d9839a9pt2.9.1cu128",
        ],
    ):
        result = subprocess.run([uv, *args], check=False)
        if result.returncode != 0:
            raise InstallLinuxError(f"uv {args[0]} failed while preparing the PyTorch3D venv")


def _download_and_verify(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            destination.write_bytes(response.read())
    except OSError as error:
        raise InstallLinuxError(f"could not download {url}: {error}") from error
    actual = hashlib.sha256(destination.read_bytes()).hexdigest()
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise InstallLinuxError(f"downloaded file from {url} did not match its pinned checksum")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=Path.home() / ".local" / "share" / "PoseCap",
    )
    parser.add_argument(
        "--components", default=None, help="comma-separated, e.g. base,mediapipe,pear"
    )
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return install_linux(
        install_dir=args.install_dir, components=args.components, base_url=args.base_url
    )


if __name__ == "__main__":
    raise SystemExit(main())
