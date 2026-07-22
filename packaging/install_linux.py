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

PEAR needs a PyTorch3D wheel. The normal path is --pytorch3d-wheel pointing
at one already built in Corridor's own pinned environment (mirrors Windows,
where the user's installer only ever installs a bundled wheel -- see
_stage_pear). Without a wheel available yet, pass
--build-pytorch3d-from-source to compile one locally as a fallback; this
needs a host CUDA/GCC/glibc toolchain compatible with CUDA 12.8 and is not
the path a normal user should need.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
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
_SUPPORT_PATH = _REPO_ROOT / "addon" / "posecap_addon" / "support.py"
_DEFAULT_BASE_URL = "https://github.com/CorridorTech/PoseCap/releases/download/local-build"


class InstallLinuxError(RuntimeError):
    """Raised when the one-command Linux install cannot proceed."""


def install_linux(
    *,
    install_dir: Path,
    components: str | None = None,
    base_url: str = _DEFAULT_BASE_URL,
    build_number: int = 1,
    cuda_home: Path | None = None,
    pytorch3d_wheel: Path | None = None,
    build_pytorch3d_from_source: bool = False,
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
                lambda: _write_installer_manifest(
                    install_dir, f"{_workspace_version()}-linux.{build_number}"
                ),
            )
            if "mediapipe" in selected:
                _step(
                    "Build and stage the MediaPipe Lite payload",
                    lambda: _stage_mediapipe(install_dir, base_url, work_dir),
                )
            if "pear" in selected:
                _step(
                    "Build and stage the PEAR payload",
                    lambda: _stage_pear(
                        install_dir,
                        base_url,
                        work_dir,
                        cuda_home or _default_cuda_home(),
                        pytorch3d_wheel,
                        build_pytorch3d_from_source,
                    ),
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


_CUDA_HOME_CANDIDATES = (
    "/usr/local/cuda-12.8",  # Debian/Ubuntu/NVIDIA .run installer convention
    "/opt/cuda",  # Arch/CachyOS pacman convention (tracks latest, no per-version package)
    "/usr/local/cuda",
)


def _default_cuda_home() -> Path:
    env_value = os.environ.get("CUDA_HOME", "").strip()
    if env_value:
        return Path(env_value)
    for candidate in _CUDA_HOME_CANDIDATES:
        path = Path(candidate)
        if path.is_dir():
            return path
    return Path(_CUDA_HOME_CANDIDATES[0])


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
    # Same hazard as _stage_pear's wheels/ clear: extractall() never removes
    # files absent from the new archive, so a stale, differently-versioned
    # workspace wheel from an earlier install would survive a version bump
    # and trip install_mediapipe.py's exact-three-wheels check.
    shutil.rmtree(target / "wheels", ignore_errors=True)
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


def _stage_pear(
    install_dir: Path,
    base_url: str,
    work_dir: Path,
    cuda_home: Path,
    pytorch3d_wheel: Path | None,
    build_pytorch3d_from_source: bool,
) -> None:
    # Normal path: a wheel already built once, in a pinned environment we
    # control -- mirrors Windows, where the user's installer only ever
    # installs a bundled wheel (see PR #98 review thread: the compile
    # happens on our release runner, never on the end user's machine).
    # Fallback: build PyTorch3D from source here, against the host's own
    # CUDA/GCC/glibc toolchain -- not the default path a normal user should
    # need, kept for people who explicitly opt in (--build-pytorch3d-from-source).
    payload_output = work_dir / "pear-payload"
    if pytorch3d_wheel is not None:
        build_pear_payload_linux.build_pear_payload_for_linux(
            base_url=base_url,
            output_dir=payload_output,
            pytorch3d_wheel=pytorch3d_wheel,
        )
    elif build_pytorch3d_from_source:
        venv_dir = work_dir / "pytorch3d-venv"
        _step(
            "  Create a throwaway venv and build PyTorch3D from source (fallback path)",
            lambda: _build_pytorch3d_venv(venv_dir, work_dir, cuda_home),
        )
        site_packages = next((venv_dir / "lib").glob("python*/site-packages"))
        build_pear_payload_linux.build_pear_payload_for_linux(
            base_url=base_url,
            output_dir=payload_output,
            pytorch3d_site_packages=site_packages,
        )
    else:
        raise InstallLinuxError(
            "no PyTorch3D wheel available for the PEAR payload. Pass --pytorch3d-wheel "
            "pointing at a prebuilt wheel (the normal path, mirroring the wheel Windows "
            "ships in its payload), or pass --build-pytorch3d-from-source to compile one "
            "locally as a fallback (needs --cuda-home and a matching host toolchain -- see "
            "doc/guides/linux-install.md)."
        )
    archives = list(payload_output.glob("posecap-pear-bootstrap-*.zip"))
    if not archives:
        raise InstallLinuxError("PEAR payload build produced no archive")

    install_dir.mkdir(parents=True, exist_ok=True)
    # wheels/ is installer-owned (component_lifecycle._PEAR_OWNED_PATHS) and
    # extractall() only overwrites files present in the new archive -- it
    # never removes ones that aren't. A prior install's PyTorch3D wheel can
    # carry a different filename (the from-source fallback embeds a git-hash
    # local version, e.g. "+d9839a9pt2.9.1cu128"; a version bump changes it
    # too), so a stale wheel from an earlier install can sit alongside the
    # new one and make the "install bundled wheels" step's `uv pip install`
    # refuse with a conflicting-package error. Clear it before extracting.
    shutil.rmtree(install_dir / "wheels", ignore_errors=True)
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(install_dir)
    (install_dir / "bin" / "uv").chmod(0o755)

    source_lock = build_pear_payload_linux._pear_source_lock()
    pear_source_target = install_dir / "payloads" / "pear" / "pear-source.zip"
    pear_source_target.parent.mkdir(parents=True, exist_ok=True)
    _download_and_verify(str(source_lock["url"]), pear_source_target, str(source_lock["sha256"]))


_PYTORCH3D_REF = "v0.7.9"
_PYTORCH3D_REPO_URL = "https://github.com/facebookresearch/pytorch3d.git"


def _build_pytorch3d_venv(venv_dir: Path, work_dir: Path, cuda_home: Path) -> None:
    """Build PyTorch3D from source against the pinned Torch matrix (fallback path).

    Mirrors tools/install/setup_pear_runtime.ps1's recipe (git clone the
    pinned ref, `pip install --no-build-isolation`) -- the same steps
    Corridor's own pinned release build runs to produce the wheel that
    ships in the normal (--pytorch3d-wheel) path. Building it here, against
    whatever CUDA/GCC/glibc toolchain happens to be on this machine, is the
    documented fallback for people who explicitly opt in
    (--build-pytorch3d-from-source) -- not what a normal install should hit.
    """
    if not cuda_home.is_dir():
        raise InstallLinuxError(
            f"CUDA Toolkit not found at {cuda_home}. Install CUDA Toolkit 12.8 there, or "
            "pass --cuda-home to an installed toolkit compatible with the Torch cu128 "
            "wheel matrix."
        )
    uv = shutil.which("uv")
    if uv is None:
        raise InstallLinuxError("uv not found on PATH")
    git = shutil.which("git")
    if git is None:
        raise InstallLinuxError("git not found on PATH")

    venv_python = venv_dir / "bin" / "python"
    result = subprocess.run([uv, "venv", str(venv_dir), "--python", "3.11"], check=False)
    if result.returncode != 0:
        raise InstallLinuxError("uv venv failed while preparing the PyTorch3D venv")

    result = subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(venv_python),
            "torch==2.9.1+cu128",
            "torchvision==0.24.1+cu128",
            "--index-url",
            "https://download.pytorch.org/whl/cu128",
        ],
        check=False,
    )
    if result.returncode != 0:
        raise InstallLinuxError("uv pip install failed while preparing the PyTorch3D venv")

    # --no-build-isolation below means the venv itself must already have
    # PyTorch3D's legacy setup.py build dependencies -- mirrors
    # setup_pear_runtime.ps1's "PEAR Python dependencies" step, which
    # installs these before the PyTorch3D build for the same reason.
    result = subprocess.run(
        [uv, "pip", "install", "--python", str(venv_python), "setuptools", "wheel", "ninja"],
        check=False,
    )
    if result.returncode != 0:
        raise InstallLinuxError("uv pip install of build dependencies failed")

    source_dir = work_dir / "pytorch3d-source"
    result = subprocess.run(
        [
            git,
            "clone",
            "--branch",
            _PYTORCH3D_REF,
            "--depth",
            "1",
            _PYTORCH3D_REPO_URL,
            str(source_dir),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise InstallLinuxError(f"git clone of PyTorch3D {_PYTORCH3D_REF} failed")

    build_env = {
        **os.environ,
        "CUDA_HOME": str(cuda_home),
        "CUB_HOME": str(cuda_home / "include"),
        "MAX_JOBS": "1",
    }
    result = subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(venv_python),
            str(source_dir),
            "--no-build-isolation",
        ],
        check=False,
        env=build_env,
    )
    if result.returncode != 0:
        raise InstallLinuxError(f"building PyTorch3D {_PYTORCH3D_REF} from source failed")


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


def _load_support_module():
    spec = importlib.util.spec_from_file_location("posecap_addon_support", _SUPPORT_PATH)
    if spec is None or spec.loader is None:
        raise InstallLinuxError(f"could not load {_SUPPORT_PATH}")
    module = importlib.util.module_from_spec(spec)
    # dataclass creation resolves the defining module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _default_install_dir() -> Path:
    """Mirror the addon's own resolver (support.py) so the installer never
    writes where the addon won't look -- e.g. when $XDG_DATA_HOME is set.
    """
    support = _load_support_module()
    paths = support.default_installation_paths(dict(os.environ))
    if paths is not None:
        return paths.root
    return Path.home() / ".local" / "share" / "PoseCap"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--install-dir",
        type=Path,
        default=_default_install_dir(),
    )
    parser.add_argument(
        "--components", default=None, help="comma-separated, e.g. base,mediapipe,pear"
    )
    parser.add_argument("--base-url", default=_DEFAULT_BASE_URL)
    parser.add_argument("--build-number", type=int, default=1)
    parser.add_argument(
        "--cuda-home",
        type=Path,
        default=_default_cuda_home(),
        help="CUDA Toolkit 12.8 install used by --build-pytorch3d-from-source",
    )
    # Not required=True: neither flag matters unless PEAR ends up selected
    # (--components can omit it, or the NVIDIA-driver autodetect can skip
    # it), and _stage_pear raises its own clear error if PEAR is selected
    # but neither was given. The group only rules out passing both at once.
    pytorch3d_source = parser.add_mutually_exclusive_group()
    pytorch3d_source.add_argument(
        "--pytorch3d-wheel",
        type=Path,
        default=None,
        help="prebuilt PyTorch3D wheel to bundle for PEAR -- the normal path",
    )
    pytorch3d_source.add_argument(
        "--build-pytorch3d-from-source",
        action="store_true",
        help="fallback: compile PyTorch3D locally against --cuda-home instead of "
        "bundling --pytorch3d-wheel; needs a matching host toolchain",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return install_linux(
        install_dir=args.install_dir,
        components=args.components,
        base_url=args.base_url,
        build_number=args.build_number,
        cuda_home=args.cuda_home,
        pytorch3d_wheel=args.pytorch3d_wheel,
        build_pytorch3d_from_source=args.build_pytorch3d_from_source,
    )


if __name__ == "__main__":
    raise SystemExit(main())
