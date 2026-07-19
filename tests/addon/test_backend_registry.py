import json
import re
from itertools import permutations
from pathlib import Path

import pytest
from posecap_addon import (
    BackendSelectionError,
    PoseBackendCatalog,
    discover_installed_pose_backends,
    discover_pose_backends,
    preferred_pose_backend,
    resolve_installed_pose_backend,
)


def _write_backend_manifest(
    registry: Path,
    backend_id: str,
    executable: Path,
    *,
    accelerators: tuple[str, ...] = ("nvidia-cuda",),
) -> Path:
    backend_dir = registry / backend_id
    backend_dir.mkdir(parents=True)
    manifest_path = backend_dir / "backend.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": backend_id,
                "display_name": f"{backend_id.upper()} (NVIDIA CUDA)",
                "command": [str(executable), "live", "--pear-root", str(registry / "pear")],
                "protocol_versions": [1],
                "capabilities": ["body", "hands", "face"],
                "compatibility": {
                    "operating_systems": ["windows", "linux"],
                    "accelerators": list(accelerators),
                    "account": "MPI account required for model downloads",
                    "license": "MPI model terms apply",
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_single_valid_pear_manifest_is_discovered_and_auto_selected(tmp_path: Path) -> None:
    executable = tmp_path / "posecap-engine.exe"
    executable.touch()
    registry = tmp_path / "backends"
    _write_backend_manifest(registry, "pear", executable)

    catalog = discover_pose_backends(registry)

    assert catalog.issues == ()
    assert catalog.selected_id == "pear"
    assert len(catalog.ready) == 1
    assert catalog.ready[0].manifest.id == "pear"
    assert catalog.ready[0].manifest.display_name == "PEAR (NVIDIA CUDA)"
    assert catalog.ready[0].manifest.command == (
        str(executable),
        "live",
        "--pear-root",
        str(registry / "pear"),
    )
    assert catalog.ready[0].manifest.protocol_versions == (1,)
    assert catalog.ready[0].manifest.capabilities == ("body", "hands", "face")
    assert catalog.ready[0].manifest.compatibility.operating_systems == ("windows", "linux")
    assert catalog.ready[0].manifest.compatibility.accelerators == ("nvidia-cuda",)
    assert catalog.ready[0].manifest.compatibility.account == (
        "MPI account required for model downloads"
    )
    assert catalog.ready[0].manifest.compatibility.license == "MPI model terms apply"


def test_automatic_prefers_the_accelerated_backend_and_yields_to_an_explicit_choice(
    tmp_path: Path,
) -> None:
    """Task 0038: Automatic picks for the user instead of refusing to choose.

    The panel offers "Automatic" as the default entry, so with the recommended
    full install (PEAR + MediaPipe) it must resolve — to the accelerated
    backend, matching the installer's own PEAR-when-NVIDIA preselection (#93).
    An explicit choice still outranks the policy.
    """
    pear_executable = tmp_path / "posecap-engine.exe"
    mediapipe_executable = tmp_path / "posecap-mediapipe.exe"
    pear_executable.touch()
    mediapipe_executable.touch()
    registry = tmp_path / "PoseCap" / "backends"
    _write_backend_manifest(registry, "pear", pear_executable)
    _write_backend_manifest(registry, "mediapipe", mediapipe_executable, accelerators=("cpu",))
    environ = {"LOCALAPPDATA": str(tmp_path)}

    automatic = resolve_installed_pose_backend(environ)

    assert automatic is not None
    assert automatic.id == "pear"

    selected = resolve_installed_pose_backend(environ, selected_id="mediapipe")

    assert selected is not None
    assert selected.id == "mediapipe"


def test_automatic_falls_back_to_the_cpu_backend_when_no_accelerated_one_is_ready(
    tmp_path: Path,
) -> None:
    """Only CPU backends installed: Automatic still resolves, it does not refuse."""
    mediapipe_executable = tmp_path / "posecap-mediapipe.exe"
    fallback_executable = tmp_path / "posecap-fallback.exe"
    mediapipe_executable.touch()
    fallback_executable.touch()
    registry = tmp_path / "PoseCap" / "backends"
    _write_backend_manifest(registry, "mediapipe", mediapipe_executable, accelerators=("cpu",))
    _write_backend_manifest(registry, "fallback", fallback_executable, accelerators=("cpu",))

    automatic = resolve_installed_pose_backend({"LOCALAPPDATA": str(tmp_path)})

    assert automatic is not None
    assert automatic.id == "fallback"


def test_preferred_pose_backend_refuses_an_empty_catalogue_with_a_domain_error() -> None:
    """The public policy must not leak a bare ValueError from ``max``."""
    empty = PoseBackendCatalog(ready=(), issues=(), selected_id=None)

    with pytest.raises(BackendSelectionError, match="No Pose Backend is ready"):
        preferred_pose_backend(empty)


@pytest.mark.parametrize("installation_order", permutations(("pear", "mediapipe", "mhr")))
def test_automatic_is_deterministic_regardless_of_installation_order(
    tmp_path: Path, installation_order: tuple[str, str, str]
) -> None:
    """The accelerated pick must not depend on which backend was installed first."""
    registry = tmp_path / "PoseCap" / "backends"
    accelerators = {
        "pear": ("nvidia-cuda",),
        "mediapipe": ("cpu",),
        "mhr": ("cpu",),
    }
    for backend_id in installation_order:
        executable = tmp_path / f"posecap-{backend_id}.exe"
        executable.touch()
        _write_backend_manifest(
            registry, backend_id, executable, accelerators=accelerators[backend_id]
        )

    automatic = resolve_installed_pose_backend({"LOCALAPPDATA": str(tmp_path)})

    assert automatic is not None
    assert automatic.id == "pear"


@pytest.mark.parametrize("installation_order", permutations(("pear", "mediapipe", "mhr")))
def test_three_backends_are_deterministic_across_installation_orders(
    tmp_path: Path, installation_order: tuple[str, str, str]
) -> None:
    registry = tmp_path / "PoseCap" / "backends"
    executables = {
        backend_id: tmp_path / f"posecap-{backend_id}.exe" for backend_id in installation_order
    }
    for executable in executables.values():
        executable.touch()
    for backend_id in installation_order:
        _write_backend_manifest(registry, backend_id, executables[backend_id])

    catalog = discover_installed_pose_backends({"LOCALAPPDATA": str(tmp_path)})
    selected = resolve_installed_pose_backend({"LOCALAPPDATA": str(tmp_path)}, selected_id="mhr")

    assert tuple(backend.manifest.id for backend in catalog.ready) == (
        "mediapipe",
        "mhr",
        "pear",
    )
    assert selected is not None
    assert selected.id == "mhr"


def test_malformed_manifest_is_isolated_without_hiding_valid_backend(tmp_path: Path) -> None:
    executable = tmp_path / "posecap-engine.exe"
    executable.touch()
    registry = tmp_path / "backends"
    _write_backend_manifest(registry, "pear", executable)
    broken_dir = registry / "broken"
    broken_dir.mkdir(parents=True)
    broken_manifest = broken_dir / "backend.json"
    broken_manifest.write_text("{not-json", encoding="utf-8")

    catalog = discover_pose_backends(registry)

    assert tuple(backend.manifest.id for backend in catalog.ready) == ("pear",)
    assert catalog.selected_id == "pear"
    assert len(catalog.issues) == 1
    assert catalog.issues[0].manifest_path == broken_manifest
    assert "invalid" in catalog.issues[0].reason


def test_unsupported_manifest_schema_is_reported_unavailable(tmp_path: Path) -> None:
    executable = tmp_path / "posecap-engine.exe"
    executable.touch()
    registry = tmp_path / "backends"
    manifest_path = _write_backend_manifest(registry, "future", executable)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["schema_version"] = 2
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    catalog = discover_pose_backends(registry)

    assert catalog.ready == ()
    assert catalog.selected_id is None
    assert len(catalog.issues) == 1
    assert "schema_version" in catalog.issues[0].reason


def test_relative_executable_is_reported_unavailable_without_being_resolved(tmp_path: Path) -> None:
    executable = tmp_path / "posecap-engine.exe"
    executable.touch()
    registry = tmp_path / "backends"
    manifest_path = _write_backend_manifest(registry, "pear", executable)
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    document["command"][0] = "posecap-engine.exe"
    manifest_path.write_text(json.dumps(document), encoding="utf-8")

    catalog = discover_pose_backends(registry)

    assert catalog.ready == ()
    assert len(catalog.issues) == 1
    assert "absolute" in catalog.issues[0].reason


def test_duplicate_backend_id_keeps_first_ready_and_reports_collision(tmp_path: Path) -> None:
    executable = tmp_path / "posecap-engine.exe"
    executable.touch()
    registry = tmp_path / "backends"
    first_manifest = _write_backend_manifest(registry, "a-pear", executable)
    first_document = json.loads(first_manifest.read_text(encoding="utf-8"))
    first_document["id"] = "pear"
    first_manifest.write_text(json.dumps(first_document), encoding="utf-8")
    duplicate_manifest = _write_backend_manifest(registry, "z-duplicate", executable)
    duplicate_document = json.loads(duplicate_manifest.read_text(encoding="utf-8"))
    duplicate_document["id"] = "PEAR"
    duplicate_manifest.write_text(json.dumps(duplicate_document), encoding="utf-8")

    catalog = discover_pose_backends(registry)

    assert tuple(backend.manifest.id for backend in catalog.ready) == ("pear",)
    assert catalog.selected_id == "pear"
    assert len(catalog.issues) == 1
    assert catalog.issues[0].manifest_path == duplicate_manifest
    assert "duplicate" in catalog.issues[0].reason


def test_installed_catalog_uses_posecap_owned_per_user_registry(tmp_path: Path) -> None:
    executable = tmp_path / "PoseCap" / "runtime" / "posecap-engine.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    registry = tmp_path / "PoseCap" / "backends"
    _write_backend_manifest(registry, "pear", executable)

    catalog = discover_installed_pose_backends({"LOCALAPPDATA": str(tmp_path)})

    assert catalog.selected_id == "pear"
    assert tuple(backend.manifest.id for backend in catalog.ready) == ("pear",)


def test_present_but_invalid_registry_never_falls_back_to_unregistered_runtime(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "PoseCap" / "backends"
    broken_dir = registry / "broken"
    broken_dir.mkdir(parents=True)
    (broken_dir / "backend.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(BackendSelectionError, match=re.escape(str(broken_dir / "backend.json"))):
        resolve_installed_pose_backend({"LOCALAPPDATA": str(tmp_path)})


def test_unreadable_registry_is_reported_as_one_catalog_issue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    registry = tmp_path / "backends"

    def _deny_glob(_path: Path, _pattern: str):
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "glob", _deny_glob)

    catalog = discover_pose_backends(registry)

    assert catalog.ready == ()
    assert catalog.selected_id is None
    assert len(catalog.issues) == 1
    assert catalog.issues[0].manifest_path == registry
    assert "access denied" in catalog.issues[0].reason
