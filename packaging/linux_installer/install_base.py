"""Install and verify the PoseCap Blender extension (Linux).

Mirrors packaging/installer/install_base.ps1: find a compatible Blender,
remove any previous PoseCap extension install, install the bundled extension
zip via Blender's own `extension` CLI, and verify it registered.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .blender_discovery import find_compatible_blenders

_INSTALLED_PATTERN = re.compile(r"(?m)^\s*posecap\s+\[installed\]")
_EXTENSION_LIST_ARGS = ("--command", "extension", "list")


class BaseInstallError(RuntimeError):
    """Raised when the Blender extension cannot be installed or verified."""


def install_base(install_dir: Path) -> None:
    """Install (or reinstall) the PoseCap extension into a discovered Blender."""
    extension_dir = install_dir / "extension"
    zips = sorted(extension_dir.glob("*.zip")) if extension_dir.is_dir() else []
    if not zips:
        raise BaseInstallError("the PoseCap Blender extension package is missing")
    extension_zip = zips[0]

    blenders = find_compatible_blenders(install_dir)
    if not blenders:
        raise BaseInstallError("Blender 4.2 or newer was not found")
    blender = blenders[0]

    if _INSTALLED_PATTERN.search(_list_extensions(blender)):
        _run(
            blender,
            ("--command", "extension", "remove", "posecap"),
            "Blender could not remove the previous PoseCap extension",
        )

    _run(
        blender,
        ("--command", "extension", "install-file", "-r", "user_default", "-e", str(extension_zip)),
        "Blender could not install the PoseCap extension",
    )
    if not _INSTALLED_PATTERN.search(_list_extensions(blender)):
        raise BaseInstallError("Blender did not report PoseCap as installed")


def _list_extensions(blender: Path) -> str:
    result = subprocess.run(
        [str(blender), *_EXTENSION_LIST_ARGS], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise BaseInstallError("Blender could not list installed extensions")
    return result.stdout + result.stderr


def _run(blender: Path, args: tuple[str, ...], failure_message: str) -> None:
    result = subprocess.run([str(blender), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise BaseInstallError(failure_message)
