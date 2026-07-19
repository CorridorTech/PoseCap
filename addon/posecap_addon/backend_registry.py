"""Discover independently installed Pose Backends from static manifests."""

from dataclasses import dataclass
from pathlib import Path

from posecap_contracts import (
    BackendManifestDecodeError,
    PoseBackendManifest,
    decode_pose_backend_manifest,
)

from .support import default_installation_paths

_CPU_ACCELERATOR = "cpu"
"""The one accelerator value that means "no dedicated hardware" (task 0038)."""


class BackendSelectionError(ValueError):
    """The installed registry exists but has no unambiguous ready backend."""


@dataclass(frozen=True)
class ReadyPoseBackend:
    """A validated backend that is safe to offer for launch."""

    manifest: PoseBackendManifest
    manifest_path: Path


@dataclass(frozen=True)
class BackendRegistryIssue:
    """One manifest excluded from the ready catalogue."""

    manifest_path: Path
    reason: str


@dataclass(frozen=True)
class PoseBackendCatalog:
    """Deterministic discovery result; invalid entries remain observable."""

    ready: tuple[ReadyPoseBackend, ...]
    issues: tuple[BackendRegistryIssue, ...]
    selected_id: str | None


def discover_installed_pose_backends(environ: dict[str, str]) -> PoseBackendCatalog:
    """Discover the fixed per-user registry created by the PoseCap installer."""
    installed = default_installation_paths(environ)
    if installed is None:
        return PoseBackendCatalog(ready=(), issues=(), selected_id=None)
    return discover_pose_backends(installed.backend_registry)


def resolve_installed_pose_backend(
    environ: dict[str, str], *, selected_id: str | None = None
) -> PoseBackendManifest | None:
    """Resolve the explicit selection, or pick automatically for the user.

    Automatic (no explicit selection) never refuses: with several ready
    backends it prefers accelerated hardware, mirroring the installer's
    PEAR-when-NVIDIA preselection (task 0038, spec 0002 amended).
    """
    installed = default_installation_paths(environ)
    if installed is None or not installed.backend_registry.is_dir():
        return None
    catalog = discover_pose_backends(installed.backend_registry)
    if catalog.selected_id is not None:
        selected = next(
            backend for backend in catalog.ready if backend.manifest.id == catalog.selected_id
        )
        return selected.manifest
    if len(catalog.ready) > 1:
        requested_id = selected_id.strip() if selected_id is not None else ""
        if requested_id:
            return _match_requested_backend(catalog, requested_id)
        return preferred_pose_backend(catalog)
    details = "; ".join(f"{issue.manifest_path}: {issue.reason}" for issue in catalog.issues)
    suffix = f": {details}" if details else ""
    raise BackendSelectionError(f"No Pose Backend is ready{suffix}")


def _is_accelerated(manifest: PoseBackendManifest) -> bool:
    """Whether the backend declares hardware acceleration rather than plain CPU.

    Read from the manifest's own compatibility facts, so a backend declaring a
    new accelerator ranks above CPU without this resolver learning its name.
    """
    return any(
        accelerator.casefold() != _CPU_ACCELERATOR
        for accelerator in manifest.compatibility.accelerators
    )


def preferred_pose_backend(catalog: PoseBackendCatalog) -> PoseBackendManifest:
    """The automatic pick: accelerated first, discovery order breaking ties.

    Public because the panel names the pick for the user rather than leaving
    "Automatic" opaque. ``discover_pose_backends`` returns ``ready`` in sorted
    manifest-path order, so equal ranks resolve the same way on every machine.

    An empty catalogue raises this module's own error rather than letting
    ``max`` surface a bare ``ValueError`` at a user-facing edge.
    """
    if not catalog.ready:
        raise BackendSelectionError("No Pose Backend is ready")
    return max(catalog.ready, key=lambda backend: _is_accelerated(backend.manifest)).manifest


def _match_requested_backend(catalog: PoseBackendCatalog, requested_id: str) -> PoseBackendManifest:
    """The ready manifest matching an explicit selection, or a user-facing error."""
    normalized_id = requested_id.casefold()
    for backend in catalog.ready:
        if backend.manifest.id.casefold() == normalized_id:
            return backend.manifest
    message = f"Selected Pose Backend '{requested_id}' is no longer ready"
    raise BackendSelectionError(f"{message}; choose one before capture")


def discover_pose_backends(registry_dir: Path) -> PoseBackendCatalog:
    """Read registered manifests without importing or executing their backends."""
    ready: list[ReadyPoseBackend] = []
    issues: list[BackendRegistryIssue] = []
    seen_ids: set[str] = set()
    try:
        manifest_paths = sorted(registry_dir.glob("*/backend.json"))
    except OSError as error:
        issue = BackendRegistryIssue(manifest_path=registry_dir, reason=str(error))
        return PoseBackendCatalog(ready=(), issues=(issue,), selected_id=None)
    for manifest_path in manifest_paths:
        try:
            manifest = decode_pose_backend_manifest(manifest_path.read_text(encoding="utf-8"))
        except (BackendManifestDecodeError, OSError) as error:
            issues.append(BackendRegistryIssue(manifest_path=manifest_path, reason=str(error)))
            continue
        executable = Path(manifest.command[0])
        if not executable.is_absolute():
            issues.append(
                BackendRegistryIssue(
                    manifest_path=manifest_path,
                    reason="backend executable path must be absolute",
                )
            )
            continue
        if not executable.is_file():
            issues.append(
                BackendRegistryIssue(
                    manifest_path=manifest_path,
                    reason="backend executable does not exist",
                )
            )
            continue
        normalized_id = manifest.id.casefold()
        if normalized_id in seen_ids:
            issues.append(
                BackendRegistryIssue(
                    manifest_path=manifest_path,
                    reason=f"duplicate backend id: {manifest.id}",
                )
            )
            continue
        seen_ids.add(normalized_id)
        ready.append(ReadyPoseBackend(manifest=manifest, manifest_path=manifest_path))

    selected_id = ready[0].manifest.id if len(ready) == 1 else None
    return PoseBackendCatalog(ready=tuple(ready), issues=tuple(issues), selected_id=selected_id)
