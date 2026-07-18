"""Install and register the isolated MediaPipe Lite Pose Backend (Linux).

Mirrors packaging/installer/install_mediapipe.ps1: an isolated CPU-only venv
under backends/mediapipe/runtime built from the same pinned wheels the
Windows payload uses, with the POSIX (bin/, no .exe) executable layout that
addon/posecap_addon/support.py's _LINUX_LAYOUT already expects.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

_REQUIRED_WHEEL_COUNT = 3


class MediaPipeInstallError(RuntimeError):
    """Raised when the MediaPipe Lite component cannot be installed or verified."""


def install_mediapipe(install_dir: Path) -> None:
    """Install the isolated MediaPipe Lite runtime and register its manifest."""
    payload_dir = install_dir / "payloads" / "mediapipe"
    uv = payload_dir / "bin" / "uv"
    wheels_dir = payload_dir / "wheels"
    lock = payload_dir / "requirements-mediapipe.lock"
    backend_dir = install_dir / "backends" / "mediapipe"
    venv_dir = backend_dir / "runtime"
    venv_python = venv_dir / "bin" / "python"
    launcher = venv_dir / "bin" / "posecap-mediapipe"
    model_path = backend_dir / "models" / "holistic_landmarker.task"
    backend_manifest_path = backend_dir / "backend.json"
    uv_env = {**os.environ, "UV_PYTHON_INSTALL_DIR": str(backend_dir / "python")}

    inventory_path = install_dir / "installed_components.json"
    if _same_version_repair(inventory_path) and _doctor_accepts_runtime(
        launcher, model_path, backend_manifest_path
    ):
        return

    _step(
        "verify the MediaPipe component payload",
        "reinstall PoseCap; the selected MediaPipe component payload is incomplete",
        lambda: _verify_payload(uv, lock, model_path, wheels_dir),
    )
    _step(
        "install Python 3.11 runtime (app-local, via uv)",
        "check your internet connection and run PoseCap Setup (repair)",
        lambda: _run_uv(uv, ("python", "install", "--no-bin", "--no-registry", "3.11"), uv_env),
    )
    _step(
        "create the isolated MediaPipe environment",
        "close Blender, then run PoseCap Setup (repair)",
        lambda: _run_uv(uv, ("venv", "--clear", "--python", "3.11", str(venv_dir)), uv_env),
    )
    _step(
        "install MediaPipe CPU dependencies",
        "check your internet connection and disk space, then run PoseCap Setup (repair)",
        lambda: _run_uv(
            uv, ("pip", "install", "--python", str(venv_python), "-r", str(lock)), uv_env
        ),
    )
    _step(
        "install PoseCap bridge",
        "reinstall PoseCap; the bundled MediaPipe component is incomplete",
        lambda: _install_wheels(uv, venv_python, wheels_dir, uv_env),
    )
    _step(
        "verify MediaPipe Lite runtime",
        "run PoseCap Setup (repair); the model or CPU runtime could not be loaded",
        lambda: _verify_runtime(launcher, model_path),
    )
    _step(
        "register MediaPipe Lite pose backend",
        "run PoseCap Setup (repair); the runtime exists but its registration failed",
        lambda: _write_backend_manifest(backend_dir, backend_manifest_path, launcher, model_path),
    )


def _step(label: str, fix: str, action: Any) -> None:
    try:
        action()
    except MediaPipeInstallError:
        raise
    except (OSError, subprocess.SubprocessError) as error:
        raise MediaPipeInstallError(f"{label} -- {error}. How to fix: {fix}") from error


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


def _doctor_accepts_runtime(launcher: Path, model_path: Path, backend_manifest_path: Path) -> bool:
    if not (launcher.is_file() and model_path.is_file() and backend_manifest_path.is_file()):
        return False
    result = subprocess.run([str(launcher), "doctor", "--model-path", str(model_path)], check=False)
    return result.returncode == 0


def _verify_payload(uv: Path, lock: Path, model_path: Path, wheels_dir: Path) -> None:
    for required in (uv, lock, model_path):
        if not required.is_file():
            raise MediaPipeInstallError(f"required component file is missing: {required}")
    wheels = list(wheels_dir.glob("*.whl")) if wheels_dir.is_dir() else []
    if len(wheels) != _REQUIRED_WHEEL_COUNT:
        raise MediaPipeInstallError(f"expected three PoseCap wheels in {wheels_dir}")


def _run_uv(uv: Path, args: tuple[str, ...], env: dict[str, str]) -> None:
    result = subprocess.run([str(uv), *args], check=False, env=env)
    if result.returncode != 0:
        raise MediaPipeInstallError(f"uv exited with code {result.returncode}")


def _install_wheels(uv: Path, venv_python: Path, wheels_dir: Path, env: dict[str, str]) -> None:
    wheels = sorted(str(path) for path in wheels_dir.glob("*.whl"))
    _run_uv(uv, ("pip", "install", "--python", str(venv_python), "--no-deps", *wheels), env)


def _verify_runtime(launcher: Path, model_path: Path) -> None:
    result = subprocess.run([str(launcher), "doctor", "--model-path", str(model_path)], check=False)
    if result.returncode != 0:
        raise MediaPipeInstallError("MediaPipe doctor reported a failing check")


def _write_backend_manifest(
    backend_dir: Path, backend_manifest_path: Path, launcher: Path, model_path: Path
) -> None:
    backend_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "id": "mediapipe",
        "display_name": "MediaPipe Lite (CPU)",
        "command": [str(launcher), "live", "--model-path", str(model_path)],
        "protocol_versions": [1],
        "capabilities": ["body"],
        "requires_body_models": False,
        "apply_orientation_fix": False,
        "compatibility": {
            "operating_systems": ["windows", "linux", "macos"],
            "accelerators": ["cpu"],
            "account": "No account required",
            "license": "Apache-2.0 (MediaPipe package and model bundle)",
        },
    }
    temp = backend_manifest_path.with_name(backend_manifest_path.name + ".tmp")
    temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temp.replace(backend_manifest_path)
