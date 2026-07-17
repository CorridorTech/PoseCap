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

MAX_LOG_FILES = 20
"""Maximum number of log files a support bundle collects.

Each log family is already rotation-bounded (1 MB x 4 files); a healthy
installation produces at most eight files, so the cap only triggers on
anomalous log directories.
"""

MAX_LOG_BYTES = 10 * 1024 * 1024
"""Maximum total log bytes a support bundle collects (10 MiB)."""

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
    """Create a local zip with diagnostics and bounded logs, never overwriting one."""
    created_at = timestamp or datetime.now(UTC)
    destination_directory.mkdir(parents=True, exist_ok=True)
    base_name = f"PoseCap-Support-{created_at:%Y%m%d-%H%M%S}"
    attempt = 0
    while True:
        output = _candidate_bundle_path(destination_directory, base_name, attempt)
        attempt += 1
        try:
            # Exclusive create makes the no-overwrite guarantee atomic; a name
            # collision is an expected retry condition here, not a failure.
            archive = zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED)
        except FileExistsError:
            continue
        try:
            with archive:
                omitted_files = _archive_logs(archive, logs_directory)
                archive.writestr("diagnostics.txt", diagnostics + _omission_note(omitted_files))
        except Exception:
            output.unlink(missing_ok=True)
            raise
        return output


def _candidate_bundle_path(directory: Path, base_name: str, attempt: int) -> Path:
    """Suffix same-second retries so every capture attempt keeps its own file."""
    if attempt == 0:
        return directory / f"{base_name}.zip"
    return directory / f"{base_name}-{attempt}.zip"


def _omission_note(omitted_files: int) -> str:
    """Describe capped log collection so support can ask for the rest."""
    if omitted_files == 0:
        return ""
    limits = f"limit: {MAX_LOG_FILES} files, {MAX_LOG_BYTES} bytes"
    return f"Log files omitted from this bundle: {omitted_files} ({limits}).{os.linesep}"


def _archive_logs(archive: zipfile.ZipFile, logs_directory: Path) -> int:
    """Add bounded PoseCap logs and the setup marker; return the omitted file count."""
    if not logs_directory.is_dir():
        return 0
    included_files = 0
    included_bytes = 0
    omitted_files = 0
    for log_path in _log_candidates(logs_directory):
        if not log_path.is_file():
            continue
        try:
            log_bytes = log_path.stat().st_size
            if included_files >= MAX_LOG_FILES or included_bytes + log_bytes > MAX_LOG_BYTES:
                omitted_files += 1
                continue
            archive.write(log_path, f"logs/{log_path.name}")
        except (FileNotFoundError, PermissionError):
            # A log rotating away or locked mid-collection is an omission;
            # any other OSError (for example disk full) is a real failure and
            # propagates to the caller's cleanup.
            omitted_files += 1
            continue
        included_files += 1
        included_bytes += log_bytes
    return omitted_files


def _log_candidates(logs_directory: Path) -> tuple[Path, ...]:
    """List the setup marker first, then logs newest first across families.

    Recency ordering means the caps drop the stalest files instead of whole
    alphabetically-later log families; the name tie-break keeps the archive
    order deterministic.
    """
    setup_marker = logs_directory / "SETUP_OK"
    markers = (setup_marker,) if setup_marker.is_file() else ()
    return markers + tuple(sorted(logs_directory.glob("*.log*"), key=_recency_key))


def _recency_key(log_path: Path) -> tuple[float, str]:
    """Sort newest first; a file vanishing mid-sort falls to the end."""
    try:
        newest_first = -log_path.stat().st_mtime
    except OSError:
        newest_first = 0.0
    return (newest_first, log_path.name)


def _looks_like_installed_engine(path: Path) -> bool:
    parts = tuple(part.casefold() for part in path.parts)
    suffix = tuple(part.casefold() for part in _ENGINE_SUBPATH)
    return len(parts) >= len(suffix) and parts[-len(suffix) :] == suffix
