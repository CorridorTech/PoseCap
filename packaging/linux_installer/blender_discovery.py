"""Discover a compatible installed Blender on Linux.

Mirrors packaging/installer/blender_discovery.ps1's search order (PATH, known
install directories, Steam) and version gate (>= 4.2), adapted to Linux's
package-manager, tarball, and Steam layouts. Flatpak/Snap Blender installs are
intentionally not covered yet: their sandboxed invocation model needs its own
decision, not a guess.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from glob import glob
from pathlib import Path

_MIN_VERSION = (4, 2)
_VERSION_PATTERN = re.compile(r"^Blender\s+(\d+)\.(\d+)(?:\.(\d+))?", re.MULTILINE)
_VERSION_TIMEOUT_SECONDS = 10


def find_compatible_blenders(install_dir: Path) -> list[Path]:
    """Return Blender >= 4.2 executables, newest first, override path first."""
    candidates: list[Path] = []
    on_path = shutil.which("blender")
    if on_path is not None:
        candidates.append(Path(on_path))
    candidates.extend(_common_install_candidates())
    candidates.extend(_steam_candidates())

    discovered = _sorted_compatible(candidates)
    override = _override_path(install_dir)
    if override is not None:
        override_version = _blender_version(override)
        if override_version is not None and override_version[:2] >= _MIN_VERSION:
            return [override, *[path for path in discovered if path != override]]
    return discovered


def _sorted_compatible(candidates: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    scored: list[tuple[tuple[int, int, int], Path]] = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        version = _blender_version(candidate)
        if version is not None and version[:2] >= _MIN_VERSION:
            scored.append((version, candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored]


def _common_install_candidates() -> list[Path]:
    home = Path.home()
    patterns = (
        "/opt/blender*/blender",
        "/opt/Blender*/blender",
        "/usr/local/blender*/blender",
        str(home / "blender*" / "blender"),
        str(home / ".local" / "blender*" / "blender"),
        # The official blender.org tarball always extracts to a "blender-*"
        # directory, but users commonly nest that inside their own organizing
        # folder (confirmed real-world layout: ~/Blender/blender-5.1.0-linux-x64/)
        # rather than extracting straight into $HOME.
        str(home / "Blender" / "blender-*" / "blender"),
        str(home / "blender" / "blender-*" / "blender"),
    )
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(Path(match) for match in sorted(glob(pattern), reverse=True))
    return matches


def _steam_candidates() -> list[Path]:
    library_roots = (
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
    )
    candidates: list[Path] = []
    seen_roots: set[Path] = set()
    for root in library_roots:
        for library_root in _steam_library_roots(root):
            if library_root in seen_roots:
                continue
            seen_roots.add(library_root)
            candidates.append(library_root / "steamapps" / "common" / "Blender" / "blender")
    return candidates


def _steam_library_roots(steam_root: Path) -> list[Path]:
    roots = [steam_root]
    library_folders = steam_root / "steamapps" / "libraryfolders.vdf"
    if library_folders.is_file():
        try:
            contents = library_folders.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return roots
        roots.extend(Path(match) for match in re.findall(r'"path"\s*"([^"]+)"', contents))
    return roots


def _blender_version(path: Path) -> tuple[int, int, int] | None:
    if not path.is_file():
        return None
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_VERSION_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    match = _VERSION_PATTERN.search(result.stdout)
    if match is None:
        return None
    major, minor, patch = match.group(1), match.group(2), match.group(3) or "0"
    return (int(major), int(minor), int(patch))


def _override_path(install_dir: Path) -> Path | None:
    """A user-chosen Blender path (setup wizard), like the Windows override file."""
    override_file = install_dir / "blender_override.txt"
    if not override_file.is_file():
        return None
    contents = override_file.read_text(encoding="utf-8").strip()
    return Path(contents) if contents else None
