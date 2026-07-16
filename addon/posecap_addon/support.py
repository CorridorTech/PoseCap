"""User-facing diagnostics and support-bundle helpers."""

from __future__ import annotations

import json
import os
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_INSTALLER_SUBPATH = ("PoseCap",)
_ENGINE_SUBPATH = ("runtime", "venv", "Scripts", "posecap-engine.exe")
_PEAR_SUBPATH = ("pear",)
_BACKEND_REGISTRY_SUBPATH = ("backends",)


@dataclass(frozen=True)
class InstallationPaths:
    """The installed runtime paths presented to users and support."""

    root: Path
    pear_root: Path
    engine_executable: Path
    backend_registry: Path
    logs: Path


def addon_version(package_file: str | Path = __file__) -> str:
    """Return the installed build label, falling back to the extension version."""
    manifest = Path(package_file).resolve().parents[1] / "blender_manifest.toml"
    try:
        with manifest.open("rb") as manifest_file:
            value = tomllib.load(manifest_file).get("version")
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"
    base_version = str(value) if isinstance(value, str) and value.strip() else "unknown"
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if base_version == "unknown" or not local_app_data:
        return base_version
    installer_manifest = Path(local_app_data, "PoseCap", "installer_manifest.json")
    try:
        with installer_manifest.open(encoding="utf-8-sig") as manifest_file:
            installed_version = json.load(manifest_file).get("version")
    except (OSError, json.JSONDecodeError, AttributeError):
        return base_version
    expected_prefix = f"{base_version}-win."
    if isinstance(installed_version, str) and installed_version.startswith(expected_prefix):
        build_number = installed_version.removeprefix(expected_prefix)
        if build_number.isdigit():
            return installed_version
    return base_version


def default_installation_paths(env: dict[str, str]) -> InstallationPaths | None:
    """Return the fixed per-user installer layout when LOCALAPPDATA is available."""
    local_app_data = env.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return None
    root = Path(local_app_data, *_INSTALLER_SUBPATH)
    return InstallationPaths(
        root=root,
        pear_root=root.joinpath(*_PEAR_SUBPATH),
        engine_executable=root.joinpath(*_ENGINE_SUBPATH),
        backend_registry=root.joinpath(*_BACKEND_REGISTRY_SUBPATH),
        logs=root / "logs",
    )


def resolve_logs_directory(
    preferences: Any,
    env: dict[str, str],
    *,
    temp_directory: str | Path | None = None,
) -> Path:
    """Keep addon and engine logs together, including custom installations."""
    pear_root = str(getattr(preferences, "pear_root", "")).strip()
    if pear_root:
        pear_path = Path(pear_root)
        if pear_path.name.casefold() == "pear" and pear_path.parent.name.casefold() == "posecap":
            return pear_path.parent / "logs"
    engine = str(getattr(preferences, "engine_executable", "")).strip()
    engine_path = Path(engine) if engine else None
    if engine_path is not None and _looks_like_installed_engine(engine_path):
        return engine_path.parents[3] / "logs"
    installed = default_installation_paths(env)
    if installed is not None and installed.root.is_dir():
        return installed.logs
    fallback = Path(temp_directory) if temp_directory else Path(tempfile.gettempdir())
    return fallback / "PoseCap" / "logs"


def diagnostic_summary(
    *,
    version: str,
    blender_version: str,
    lifecycle_state: str,
    pear_root: str,
    engine_executable: str,
    logs_directory: Path,
) -> str:
    """Build a compact, copyable readiness report without credentials."""
    pear = Path(pear_root) if pear_root else None
    engine = Path(engine_executable) if engine_executable else None
    lines = (
        f"PoseCap version: {version}",
        f"Blender version: {blender_version}",
        f"Capture state: {lifecycle_state}",
        f"PEAR root: {pear_root or 'not detected'}",
        f"PEAR root exists: {bool(pear and pear.is_dir())}",
        f"Engine executable: {engine_executable or 'not detected'}",
        f"Engine executable exists: {bool(engine and engine.is_file())}",
        f"Logs directory: {logs_directory}",
    )
    return os.linesep.join(lines) + os.linesep


def create_support_bundle(
    *,
    destination_directory: Path,
    logs_directory: Path,
    diagnostics: str,
    timestamp: datetime | None = None,
) -> Path:
    """Create a local zip containing diagnostics and bounded PoseCap logs."""
    created_at = timestamp or datetime.now(UTC)
    destination_directory.mkdir(parents=True, exist_ok=True)
    output = destination_directory / f"PoseCap-Support-{created_at:%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("diagnostics.txt", diagnostics)
        _archive_logs(archive, logs_directory)
    return output


def _archive_logs(archive: zipfile.ZipFile, logs_directory: Path) -> None:
    """Add bounded PoseCap logs and the setup marker to the bundle."""
    if not logs_directory.is_dir():
        return
    for log_path in sorted(logs_directory.glob("*.log*")):
        if log_path.is_file():
            archive.write(log_path, f"logs/{log_path.name}")
    setup_marker = logs_directory / "SETUP_OK"
    if setup_marker.is_file():
        archive.write(setup_marker, "logs/SETUP_OK")


def _looks_like_installed_engine(path: Path) -> bool:
    parts = tuple(part.casefold() for part in path.parts)
    suffix = tuple(part.casefold() for part in _ENGINE_SUBPATH)
    return len(parts) >= len(suffix) and parts[-len(suffix) :] == suffix
