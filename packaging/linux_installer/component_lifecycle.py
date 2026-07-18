"""Installed-component inventory and safe deselection cleanup (Linux).

Mirrors packaging/installer/component_lifecycle.ps1's JSON schema and
behavior field-for-field, so installed_components.json stays a shared
cross-platform contract per ADR-0011 ("other operating systems... reuse the
component, inventory, and manifest contracts... through their native
packaging surface").
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
VALID_COMPONENT_SELECTIONS = (
    "base",
    "base,mediapipe",
    "base,pear",
    "base,mediapipe,pear",
)

_BASE_OWNED_PATHS = (
    "bootstrap",
    "extension",
    "installer_manifest.json",
    "pear_payload_manifest.json",
    "mediapipe_payload_manifest.json",
    "installed_components.json",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)
_MEDIAPIPE_OWNED_PATHS = ("payloads/mediapipe", "backends/mediapipe")
_PEAR_OWNED_PATHS = (
    "bin",
    "wheels",
    "requirements-torch.lock",
    "requirements-pypi.lock",
    "payloads/pear",
    "python",
    "runtime",
    "backends/pear",
)
# The user's own downloaded PEAR source + licensed model assets live under
# "pear" -- never deleted on deselection, unlike the runtime/wheels above.
_PEAR_RETAINED_DATA_PATHS = ("pear",)


class ComponentLifecycleError(RuntimeError):
    """Raised for an invalid component selection or a malformed inventory."""


def parse_selected_components(components: str) -> tuple[str, ...]:
    """Validate and split a comma-separated component selection."""
    selected = tuple(components.split(","))
    if ",".join(selected) not in VALID_COMPONENT_SELECTIONS:
        raise ComponentLifecycleError(f"invalid component selection {components!r}")
    return selected


def read_installed_inventory(install_dir: Path) -> dict[str, Any] | None:
    """Return the installed-component inventory, or None if none exists yet."""
    inventory_path = install_dir / "installed_components.json"
    if not inventory_path.is_file():
        return None
    try:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ComponentLifecycleError(
            f"malformed installed component inventory at '{inventory_path}': {error}"
        ) from error
    if (
        not isinstance(inventory, dict)
        or inventory.get("schema_version") != SCHEMA_VERSION
        or not isinstance(inventory.get("components"), dict)
    ):
        raise ComponentLifecycleError(
            f"malformed installed component inventory at '{inventory_path}': unsupported schema"
        )
    return inventory


def write_installed_inventory(install_dir: Path, inventory: dict[str, Any]) -> None:
    """Write the inventory atomically (temp file + replace)."""
    install_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = install_dir / "installed_components.json"
    temp_path = inventory_path.with_name(inventory_path.name + ".tmp")
    temp_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    temp_path.replace(inventory_path)


def begin(install_dir: Path, components: str, version: str) -> None:
    """Start an install/repair transaction and clean up deselected components."""
    selected = parse_selected_components(components)
    previous = read_installed_inventory(install_dir)
    previous_version = str(previous["version"]) if previous is not None else None

    component_inventory: dict[str, Any] = {
        "base": {
            "version": version,
            "state": "installing",
            "owned_paths": list(_BASE_OWNED_PATHS),
            "manifest": {"state": "not_applicable", "path": None},
        }
    }
    if "mediapipe" in selected:
        component_inventory["mediapipe"] = {
            "version": version,
            "state": "installing",
            "owned_paths": list(_MEDIAPIPE_OWNED_PATHS),
            "manifest": {"state": "pending", "path": "backends/mediapipe/backend.json"},
        }
    if "pear" in selected:
        component_inventory["pear"] = {
            "version": version,
            "state": "installing",
            "owned_paths": list(_PEAR_OWNED_PATHS),
            "retained_data_paths": list(_PEAR_RETAINED_DATA_PATHS),
            "manifest": {"state": "pending", "path": "backends/pear/backend.json"},
        }

    write_installed_inventory(
        install_dir,
        {
            "schema_version": SCHEMA_VERSION,
            "version": version,
            "transaction_state": "installing",
            "previous_version": previous_version,
            "components": component_inventory,
        },
    )

    previously_had_mediapipe = (
        _inventory_has_component(previous, "mediapipe")
        or (install_dir / "backends" / "mediapipe" / "backend.json").is_file()
    )
    if previously_had_mediapipe and "mediapipe" not in selected:
        for owned_path in _MEDIAPIPE_OWNED_PATHS:
            _remove_installer_owned_tree(install_dir, owned_path)

    previously_had_pear = (
        _inventory_has_component(previous, "pear")
        or (install_dir / "backends" / "pear" / "backend.json").is_file()
    )
    if previously_had_pear and "pear" not in selected:
        for owned_path in _PEAR_OWNED_PATHS:
            _remove_installer_owned_tree(install_dir, owned_path)


def base_ready(install_dir: Path) -> None:
    """Mark the base component ready once the extension install succeeds."""
    inventory = _require_installing_inventory(install_dir)
    inventory["components"]["base"]["state"] = "ready"
    write_installed_inventory(install_dir, inventory)


def complete(install_dir: Path, components: str) -> None:
    """Finish the transaction once every selected component is registered."""
    selected = parse_selected_components(components)
    inventory = _require_installing_inventory(install_dir)
    recorded_names = tuple(inventory["components"].keys())
    if recorded_names != selected:
        raise ComponentLifecycleError("component selection changed during installation")
    for name in selected:
        if name == "base":
            continue
        backend_manifest = install_dir / "backends" / name / "backend.json"
        if not backend_manifest.is_file():
            raise ComponentLifecycleError(
                f"{name} was selected but its backend manifest is missing"
            )
        inventory["components"][name]["manifest"]["state"] = "registered"
    for name in recorded_names:
        inventory["components"][name]["state"] = "ready"
    inventory["transaction_state"] = "ready"
    inventory.pop("previous_version", None)
    write_installed_inventory(install_dir, inventory)


def _require_installing_inventory(install_dir: Path) -> dict[str, Any]:
    inventory = read_installed_inventory(install_dir)
    if inventory is None or inventory.get("transaction_state") != "installing":
        raise ComponentLifecycleError(
            "cannot complete component lifecycle without an installing inventory"
        )
    return inventory


def _inventory_has_component(inventory: dict[str, Any] | None, name: str) -> bool:
    if inventory is None:
        return False
    components = inventory.get("components")
    return isinstance(components, dict) and name in components


def _remove_installer_owned_tree(install_dir: Path, relative_path: str) -> None:
    """Delete a path the installer owns, refusing to escape the install root."""
    root = install_dir.resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ComponentLifecycleError(
            f"refusing to remove path outside the PoseCap install root: '{target}'"
        )
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
