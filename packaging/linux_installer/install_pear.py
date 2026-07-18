"""Install and register the PEAR (NVIDIA CUDA) Pose Backend (Linux).

Mirrors packaging/installer/install_pear.ps1: an NVIDIA driver check, an
app-local Python 3.11 + CUDA venv via uv, the pinned torch/torchvision/
PyTorch3D matrix (ADR-0016), the external PEAR source archive (never
vendored, ADR-0005), YOLO detector weights, backend registration, and a
doctor verification pass that tolerates a "licensed assets missing" failure
as an install-complete-but-action-required state rather than a hard error --
the SMPL-X/FLAME/MANO models are never bundled and must come from the user's
own MPI account (doc/guides/smplx-model-setup.md).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from .nvidia_detect import nvidia_driver_present

_REQUIRED_PEAR_PATHS = ("models", "utils", "configs/infer.yaml")
_MIN_BUNDLED_WHEELS = 4


class PearInstallError(RuntimeError):
    """Raised when the PEAR component cannot be installed or verified."""


def install_pear(install_dir: Path) -> None:
    """Install the PEAR runtime, fetch its source, and register its manifest."""
    uv = install_dir / "bin" / "uv"
    wheels_dir = install_dir / "wheels"
    python_dir = install_dir / "python"
    venv_dir = install_dir / "runtime" / "venv"
    venv_python = venv_dir / "bin" / "python"
    engine_path = venv_dir / "bin" / "posecap-engine"
    pear_dir = install_dir / "pear"
    manifest_path = install_dir / "installer_manifest.json"
    inventory_path = install_dir / "installed_components.json"
    pear_backend_dir = install_dir / "backends" / "pear"
    pear_backend_manifest_path = pear_backend_dir / "backend.json"
    pear_source_archive = install_dir / "payloads" / "pear" / "pear-source.zip"
    uv_env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(python_dir)}

    manifest = _read_installer_manifest(manifest_path)

    if _same_version_repair(inventory_path) and _doctor_accepts_runtime(
        venv_python, pear_dir, pear_backend_manifest_path
    ):
        print("PEAR runtime is healthy and already matches this installer; preserving it.")
        return

    _step(
        "check NVIDIA driver (nvidia-smi)",
        "install the NVIDIA driver for your GPU, then run PoseCap Setup (repair)",
        _check_nvidia_driver,
    )
    _step(
        "install Python 3.11 runtime (app-local, via uv)",
        "check your internet connection and re-run setup",
        lambda: _run_uv(uv, ("python", "install", "--no-bin", "--no-registry", "3.11"), uv_env),
    )
    _step(
        "create engine virtual environment",
        f"delete '{venv_dir}' and re-run setup",
        lambda: _run_uv(uv, ("venv", "--clear", "--python", "3.11", str(venv_dir)), uv_env),
    )
    _step(
        "install PyTorch CUDA wheels (~2.5 GB download)",
        "check your internet connection and disk space (needs ~8 GB free), then re-run setup",
        lambda: _run_uv(
            uv,
            (
                "pip",
                "install",
                "--python",
                str(venv_python),
                "--index-url",
                str(manifest["torchIndexUrl"]),
                "-r",
                str(install_dir / "requirements-torch.lock"),
            ),
            uv_env,
        ),
    )
    _step(
        "install engine dependencies",
        "check your internet connection, then re-run setup",
        lambda: _run_uv(
            uv,
            (
                "pip",
                "install",
                "--python",
                str(venv_python),
                "-r",
                str(install_dir / "requirements-pypi.lock"),
            ),
            uv_env,
        ),
    )
    _step(
        "install bundled wheels (PoseCap engine + PyTorch3D)",
        "reinstall PoseCap; the bundled wheels are missing or corrupt",
        lambda: _install_wheels(uv, venv_python, wheels_dir, uv_env),
    )
    _step(
        f"fetch PEAR model code (pinned revision {manifest.get('pearRevision')})",
        "re-run the installer; the verified PEAR component payload is incomplete",
        lambda: _fetch_pear_source(pear_source_archive, pear_dir, str(manifest["pearRevision"])),
    )
    _step(
        "fetch YOLO person-detection weights",
        "check your internet connection, then re-run setup",
        lambda: _fetch_yolo_weights(venv_python, pear_dir),
    )
    _step(
        "register PEAR pose backend",
        "run PoseCap Setup (repair); the runtime exists but its registration failed",
        lambda: _write_backend_manifest(
            pear_backend_dir, pear_backend_manifest_path, engine_path, pear_dir
        ),
    )

    licensed_models_pending = _verify_and_download_weights(venv_python, pear_dir)
    if licensed_models_pending:
        print()
        print("ACTION REQUIRED - licensed body models (one-time):")
        print("SMPL/SMPL-X/FLAME body models cannot ship with PoseCap.")
        print("Use Blender's PoseCap > Body Models setup, then run PoseCap Doctor.")
        print("  https://github.com/CorridorTech/PoseCap/blob/main/doc/guides/smplx-model-setup.md")


def _step(label: str, fix: str, action: Any) -> None:
    print(f"\n==> {label}")
    try:
        action()
    except PearInstallError:
        raise
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        raise PearInstallError(f"{label} -- {error}. How to fix: {fix}") from error


def _read_installer_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file():
        raise PearInstallError(f"installer_manifest.json not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise PearInstallError(f"installer_manifest.json at {manifest_path} is not an object")
    return manifest


def _same_version_repair(inventory_path: Path) -> bool:
    if not inventory_path.is_file():
        return False
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(inventory, dict):
        return False
    previous_version = inventory.get("previous_version")
    return (
        inventory.get("transaction_state") == "installing"
        and previous_version is not None
        and str(previous_version) == str(inventory.get("version"))
    )


def _doctor_accepts_runtime(venv_python: Path, pear_dir: Path, backend_manifest_path: Path) -> bool:
    if not (
        venv_python.is_file()
        and (pear_dir / "configs" / "infer.yaml").is_file()
        and backend_manifest_path.is_file()
    ):
        return False
    ok, tolerable = _run_doctor(venv_python, pear_dir, download_weights=False)
    return ok or tolerable


def _check_nvidia_driver() -> None:
    if not nvidia_driver_present():
        raise PearInstallError("nvidia-smi not found or unhealthy -- no NVIDIA driver detected")


def _run_uv(uv: Path, args: tuple[str, ...], env: dict[str, str]) -> None:
    result = subprocess.run([str(uv), *args], check=False, env=env)
    if result.returncode != 0:
        raise PearInstallError(f"uv exited with code {result.returncode}")


def _install_wheels(uv: Path, venv_python: Path, wheels_dir: Path, env: dict[str, str]) -> None:
    wheels = sorted(str(path) for path in wheels_dir.glob("*.whl"))
    if len(wheels) < _MIN_BUNDLED_WHEELS:
        raise PearInstallError(
            f"expected at least {_MIN_BUNDLED_WHEELS} bundled wheels in {wheels_dir}"
        )
    _run_uv(uv, ("pip", "install", "--python", str(venv_python), *wheels), env)


def _fetch_pear_source(source_archive: Path, pear_dir: Path, expected_revision: str) -> None:
    revision_marker = pear_dir / ".posecap-source-revision"
    marker = pear_dir / "configs" / "infer.yaml"
    installed_revision = (
        revision_marker.read_text(encoding="utf-8").strip() if revision_marker.is_file() else ""
    )
    if marker.is_file() and installed_revision == expected_revision:
        print("    already present -- preserving code and user-acquired data")
        return
    if not source_archive.is_file():
        raise PearInstallError(f"verified PEAR source archive not found at {source_archive}")

    extraction_root = Path(tempfile.mkdtemp(prefix="posecap-pear-extract-"))
    try:
        with zipfile.ZipFile(source_archive) as archive:
            top_level_dirs = {name.split("/", 1)[0] for name in archive.namelist() if name}
            if len(top_level_dirs) != 1:
                raise PearInstallError(
                    "PEAR archive did not contain exactly one top-level directory"
                )
            inner_name = next(iter(top_level_dirs))
            for required in _REQUIRED_PEAR_PATHS:
                if not any(
                    name.startswith(f"{inner_name}/{required}") for name in archive.namelist()
                ):
                    raise PearInstallError(f"PEAR archive is missing expected path '{required}'")
            archive.extractall(extraction_root)
        extracted = extraction_root / inner_name
        # dirs_exist_ok=True merges into an already-populated pear_dir (e.g. a
        # prior checkout, or the user's own licensed model assets under
        # assets/) instead of failing or clobbering it -- a plain rename()
        # over an existing non-empty directory raises ENOTEMPTY, and the
        # licensed assets must never be deleted just because they aren't part
        # of the fresh PEAR source archive.
        pear_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(extracted, pear_dir, dirs_exist_ok=True)
    finally:
        shutil.rmtree(extraction_root, ignore_errors=True)

    for required in _REQUIRED_PEAR_PATHS:
        if not (pear_dir / required).exists():
            raise PearInstallError(f"PEAR checkout is missing expected path '{required}'")
    (pear_dir / ".posecap-source-revision").write_text(expected_revision, encoding="utf-8")


def _fetch_yolo_weights(venv_python: Path, pear_dir: Path) -> None:
    model_zoo = pear_dir / "model_zoo"
    yolo_weights = model_zoo / "yolov8s.pt"
    if yolo_weights.is_file():
        print("    already present -- skipping download")
        return
    model_zoo.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(venv_python), "-c", "from ultralytics import YOLO; YOLO('yolov8s.pt')"],
        cwd=model_zoo,
        check=False,
    )
    if result.returncode != 0:
        raise PearInstallError(f"ultralytics download exited with code {result.returncode}")
    if not yolo_weights.is_file():
        raise PearInstallError(f"yolov8s.pt did not appear in {model_zoo}")


def _write_backend_manifest(
    backend_dir: Path, backend_manifest_path: Path, engine_path: Path, pear_dir: Path
) -> None:
    # Registration means "component installed", not "runtime healthy": an
    # unsupported-GPU or missing-asset runtime can still be fixed later and
    # become selectable in Blender once repaired. The addon registry
    # validates every manifest on read; the live-stream start path surfaces
    # the doctor-grade diagnostic for a broken runtime.
    backend_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "id": "pear",
        "display_name": "PEAR (NVIDIA CUDA)",
        "command": [str(engine_path), "live", "--pear-root", str(pear_dir)],
        "protocol_versions": [1],
        "capabilities": ["body", "hands", "face"],
        "compatibility": {
            "operating_systems": ["linux"],
            "accelerators": ["nvidia-cuda"],
            "account": "MPI account required for model downloads",
            "license": "MPI model terms apply; commercial use requires a Meshcapade license",
        },
    }
    temp = backend_manifest_path.with_name(backend_manifest_path.name + ".tmp")
    temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temp.replace(backend_manifest_path)


def _verify_and_download_weights(venv_python: Path, pear_dir: Path) -> bool:
    """Return whether the only remaining gap is the licensed asset files."""
    ok, tolerable = _run_doctor(venv_python, pear_dir, download_weights=True)
    if ok:
        return False
    if tolerable:
        return True
    raise PearInstallError("doctor reported failing checks")


def _run_doctor(venv_python: Path, pear_dir: Path, *, download_weights: bool) -> tuple[bool, bool]:
    """Run `posecap_engine.cli doctor`; return (ok, tolerable-failure)."""
    args = [str(venv_python), "-m", "posecap_engine.cli", "doctor", "--pear-root", str(pear_dir)]
    if download_weights:
        args.append("--download-weights")
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    print(result.stdout)
    if result.stderr.strip():
        print(result.stderr)
    if result.returncode == 0:
        return True, False
    try:
        report = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return False, False
    errors = [check["name"] for check in report.get("checks", []) if check.get("status") == "error"]
    tolerable = len(errors) >= 1 and all(name == "pear_assets" for name in errors)
    return False, tolerable
