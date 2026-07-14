"""Manifest contract for independently installed Pose Backends."""

import json
import re
from dataclasses import dataclass
from typing import cast

from .errors import BackendManifestDecodeError

BACKEND_MANIFEST_SCHEMA_VERSION = 1
_BACKEND_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")


@dataclass(frozen=True)
class BackendCompatibility:
    """User-facing compatibility facts declared by a backend installer."""

    operating_systems: tuple[str, ...]
    accelerators: tuple[str, ...]
    account: str
    license: str


@dataclass(frozen=True)
class PoseBackendManifest:
    """Static description of one isolated Pose Backend process."""

    schema_version: int
    id: str
    display_name: str
    command: tuple[str, ...]
    protocol_versions: tuple[int, ...]
    capabilities: tuple[str, ...]
    compatibility: BackendCompatibility
    requires_body_models: bool = True
    apply_orientation_fix: bool = True


def decode_pose_backend_manifest(text: str) -> PoseBackendManifest:
    """Decode one backend manifest without importing or executing backend code."""
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as error:
        raise BackendManifestDecodeError(f"invalid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise BackendManifestDecodeError("Pose Backend manifest must be a JSON object")
    raw = cast("dict[object, object]", parsed)
    document = {str(key): value for key, value in raw.items()}

    schema_version = document.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != BACKEND_MANIFEST_SCHEMA_VERSION:
        raise BackendManifestDecodeError(
            "unsupported schema_version "
            f"{schema_version!r}; expected {BACKEND_MANIFEST_SCHEMA_VERSION}"
        )
    backend_id = _require_nonempty_string(document, "id")
    if _BACKEND_ID_PATTERN.fullmatch(backend_id) is None:
        raise BackendManifestDecodeError("id must contain only letters, digits, '.', '_' or '-'")
    compatibility = _require_object(document, "compatibility")
    return PoseBackendManifest(
        schema_version=BACKEND_MANIFEST_SCHEMA_VERSION,
        id=backend_id,
        display_name=_require_nonempty_string(document, "display_name"),
        command=_require_string_tuple(document, "command"),
        protocol_versions=_require_protocol_versions(document),
        capabilities=_require_string_tuple(document, "capabilities", unique=True),
        compatibility=BackendCompatibility(
            operating_systems=_require_string_tuple(
                compatibility, "operating_systems", unique=True
            ),
            accelerators=_require_string_tuple(compatibility, "accelerators", unique=True),
            account=_require_nonempty_string(compatibility, "account"),
            license=_require_nonempty_string(compatibility, "license"),
        ),
        requires_body_models=_optional_bool(document, "requires_body_models", default=True),
        apply_orientation_fix=_optional_bool(document, "apply_orientation_fix", default=True),
    )


def _require_object(document: dict[str, object], field: str) -> dict[str, object]:
    value = document.get(field)
    if not isinstance(value, dict):
        raise BackendManifestDecodeError(f"{field} must be an object")
    items = cast("dict[object, object]", value)
    return {str(key): item for key, item in items.items()}


def _optional_bool(document: dict[str, object], field: str, *, default: bool) -> bool:
    value = document.get(field, default)
    if not isinstance(value, bool):
        raise BackendManifestDecodeError(f"{field} must be a boolean")
    return value


def _require_nonempty_string(document: dict[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise BackendManifestDecodeError(f"{field} must be a non-empty string")
    return value


def _require_string_tuple(
    document: dict[str, object], field: str, *, unique: bool = False
) -> tuple[str, ...]:
    value = document.get(field)
    if not isinstance(value, list) or not value:
        raise BackendManifestDecodeError(f"{field} must be a non-empty array of strings")
    items = cast("list[object]", value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise BackendManifestDecodeError(f"{field} must be a non-empty array of strings")
    strings = cast("list[str]", items)
    if unique and len({item.casefold() for item in strings}) != len(strings):
        raise BackendManifestDecodeError(f"{field} entries must be unique")
    return tuple(strings)


def _require_protocol_versions(document: dict[str, object]) -> tuple[int, ...]:
    value = document.get("protocol_versions")
    if not isinstance(value, list) or not value:
        raise BackendManifestDecodeError("protocol_versions must be a non-empty array")
    items = cast("list[object]", value)
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in items):
        raise BackendManifestDecodeError("protocol_versions must contain positive integers")
    versions = cast("list[int]", items)
    if len(set(versions)) != len(versions):
        raise BackendManifestDecodeError("protocol_versions entries must be unique")
    return tuple(versions)
