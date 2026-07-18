"""PoseCap modular post-install coordinator (Linux).

Mirrors packaging/installer/bootstrap_install.ps1's sequence: begin the
component transaction, install the Blender extension, mark base ready,
install any selected optional components, then complete the transaction and
drop a SETUP_OK marker. Assumes the payload layout (extension zip, MediaPipe
payload, PEAR payload) is already staged under install_dir -- staging it is a
separate, not-yet-built Linux payload/download step (see
doc/linux-support/PROGRESS.md).

Default component selection has no GUI wizard to drive it on Linux (unlike
Windows's Inno Setup NvidiaDriverPresent check), so an unspecified
--components defaults to MediaPipe always (account-free) plus PEAR too when
nvidia-smi reports a healthy driver -- same preselection outcome as Windows,
different mechanism.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import component_lifecycle
from .install_base import BaseInstallError, install_base
from .install_mediapipe import MediaPipeInstallError, install_mediapipe
from .install_pear import PearInstallError, install_pear
from .nvidia_detect import nvidia_driver_present


class BootstrapError(RuntimeError):
    """Raised when setup cannot proceed at all (missing/invalid manifest)."""


def bootstrap_install(install_dir: Path, components: str | None = None) -> int:
    """Run the full component install sequence; return a process exit code."""
    log_dir = install_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        selected_components = _resolve_components(install_dir, components)
        selected = component_lifecycle.parse_selected_components(selected_components)
        manifest = _read_installer_manifest(install_dir)
        version = str(manifest["version"])

        component_lifecycle.begin(install_dir, selected_components, version)
        install_base(install_dir)
        component_lifecycle.base_ready(install_dir)
        if "mediapipe" in selected:
            install_mediapipe(install_dir)
        if "pear" in selected:
            install_pear(install_dir)
        component_lifecycle.complete(install_dir, selected_components)
        (log_dir / "SETUP_OK").write_text(datetime.now(UTC).isoformat(), encoding="ascii")
    except (
        BootstrapError,
        component_lifecycle.ComponentLifecycleError,
        BaseInstallError,
        MediaPipeInstallError,
        PearInstallError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"SETUP FAILED: {error}", file=sys.stderr)
        print(
            "Run PoseCap Setup (repair), then share the newest log if it still fails.",
            file=sys.stderr,
        )
        return 1

    print("PoseCap setup complete.")
    print("Open Blender, press N in the 3D Viewport, and choose the PoseCap tab.")
    print("PoseCap lists installed pose backends in its panel; choose one when several are ready.")
    return 0


def _resolve_components(install_dir: Path, components: str | None) -> str:
    if components:
        return components
    inventory = component_lifecycle.read_installed_inventory(install_dir)
    if inventory is not None:
        return ",".join(inventory["components"].keys())
    return _default_components()


def _default_components() -> str:
    """MediaPipe is always recommended; PEAR joins it when a healthy NVIDIA
    driver is present -- the no-wizard equivalent of the Windows installer's
    NvidiaDriverPresent preselection."""
    if nvidia_driver_present():
        return "base,mediapipe,pear"
    return "base,mediapipe"


def _read_installer_manifest(install_dir: Path) -> dict[str, object]:
    manifest_path = install_dir / "installer_manifest.json"
    if not manifest_path.is_file():
        raise BootstrapError(f"installer_manifest.json not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or "version" not in manifest:
        raise BootstrapError(f"installer_manifest.json at {manifest_path} is missing 'version'")
    return manifest


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="posecap-linux-installer")
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--components", default=None, help="comma-separated, e.g. base,mediapipe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return bootstrap_install(args.install_dir, args.components)


if __name__ == "__main__":
    raise SystemExit(main())
