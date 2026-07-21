"""Contract tests for the native Linux installer (packaging/linux_installer/).

Unlike the Windows contract tests in test_installer_components.py (gated to
sys.platform == "win32" and shelling out to real powershell.exe), the
package under test here is pure Python and platform-neutral. The tests
themselves are not, though: the fixtures below fake out `blender`/`uv` as
POSIX shebang scripts marked executable via chmod, which Windows cannot
run (extensionless files aren't executable, and chmod's exec bits are a
no-op there) -- so this module is gated to POSIX and runs on Linux CI
(ubuntu-latest), which is exactly where it matters most.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

import build_mediapipe_payload_linux
import pytest
from linux_installer import bootstrap_install as bootstrap_install_module
from linux_installer import component_lifecycle
from linux_installer.blender_discovery import find_compatible_blenders
from linux_installer.install_base import BaseInstallError, install_base
from linux_installer.install_mediapipe import MediaPipeInstallError, install_mediapipe
from linux_installer.install_pear import PearInstallError, _fetch_pear_source, install_pear
from linux_installer.nvidia_detect import nvidia_driver_present
from posecap_contracts import decode_pose_backend_manifest

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="fixtures are POSIX executable shebang scripts"
)


def _prepend_to_path(monkeypatch: pytest.MonkeyPatch, directory: Path) -> None:
    """Put `directory` first on PATH without breaking the fake scripts'
    #!/usr/bin/env python3 shebang, which needs the real PATH to resolve
    python3 -- a plain setenv("PATH", directory) would hide it."""
    monkeypatch.setenv("PATH", str(directory) + os.pathsep + os.environ.get("PATH", ""))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate Path.home() so blender_discovery's home-relative glob patterns
    never pick up whatever real Blender install happens to exist on the
    machine actually running these tests (real gap: these patterns started
    matching this dev machine's own ~/Blender/blender-5.1.0-linux-x64/ once
    they were widened to find it)."""
    home = tmp_path / "isolated-home"
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


def _write_executable(path: Path, script: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


_BLENDER_STUB = """#!/usr/bin/env python3
import sys
from pathlib import Path

marker = Path(__file__).parent / "posecap-installed.txt"
args = sys.argv[1:]
if args == ["--version"]:
    print("Blender {version}")
    sys.exit(0)
if {fail_commands} and len(args) > 1:
    print("fixture: extension command failed", file=sys.stderr)
    sys.exit(3)
if args == ["--command", "extension", "list"]:
    if marker.is_file():
        print("posecap [installed]")
    sys.exit(0)
if args[:3] == ["--command", "extension", "install-file"]:
    marker.write_text("installed")
    sys.exit(0)
if args == ["--command", "extension", "remove", "posecap"]:
    marker.unlink(missing_ok=True)
    sys.exit(0)
print("Unexpected arguments: " + " ".join(args), file=sys.stderr)
sys.exit(2)
"""


def _fake_blender(path: Path, *, version: str = "4.2.1", fail_commands: bool = False) -> None:
    _write_executable(path, _BLENDER_STUB.format(version=version, fail_commands=fail_commands))


_UV_STUB = """#!/usr/bin/env python3
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:2] == ["python", "install"]:
    sys.exit(0)
if args and args[0] == "venv":
    Path(args[-1], "bin").mkdir(parents=True, exist_ok=True)
    sys.exit(0)
if args[:2] == ["pip", "install"]:
    python_index = args.index("--python")
    venv_python = Path(args[python_index + 1])
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("#!/usr/bin/env python3\\n")
    venv_python.chmod(0o755)
    launcher = venv_python.parent / "posecap-mediapipe"
    if not launcher.is_file():
        launcher.write_text("#!/usr/bin/env python3\\nimport sys\\nsys.exit(0)\\n")
        launcher.chmod(0o755)
sys.exit(0)
"""


def _fake_uv(path: Path) -> None:
    _write_executable(path, _UV_STUB)


def _mediapipe_payload(payload_dir: Path) -> None:
    _fake_uv(payload_dir / "bin" / "uv")
    (payload_dir / "requirements-mediapipe.lock").write_text("mediapipe==0.10.35\n")
    wheels_dir = payload_dir / "wheels"
    wheels_dir.mkdir(parents=True)
    for name in ("posecap_contracts", "posecap_core", "posecap_engine"):
        (wheels_dir / f"{name}-1.0.0-py3-none-any.whl").write_bytes(b"fixture")


# --- blender_discovery -----------------------------------------------------


def test_finds_a_blender_on_path_meeting_the_version_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blender = tmp_path / "bin" / "blender"
    _fake_blender(blender, version="4.2.1")
    _prepend_to_path(monkeypatch, blender.parent)

    found = find_compatible_blenders(tmp_path)

    assert found == [blender]


def test_excludes_a_blender_below_the_minimum_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blender = tmp_path / "bin" / "blender"
    _fake_blender(blender, version="4.1.9")
    _prepend_to_path(monkeypatch, blender.parent)

    assert find_compatible_blenders(tmp_path) == []


def test_override_file_outranks_a_discovered_blender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path = tmp_path / "bin" / "blender"
    _fake_blender(on_path, version="4.2.1")
    _prepend_to_path(monkeypatch, on_path.parent)
    override = tmp_path / "custom" / "blender"
    _fake_blender(override, version="5.0.0")
    (tmp_path / "blender_override.txt").write_text(str(override))

    assert find_compatible_blenders(tmp_path) == [override, on_path]


def test_finds_a_blender_nested_under_a_wrapper_directory(
    tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real layout found via field testing: the official blender.org tarball
    # extracted into a personal organizing folder rather than straight into
    # $HOME (~/Blender/blender-5.1.0-linux-x64/blender).
    _prepend_to_path(monkeypatch, tmp_path / "empty")
    blender = isolated_home / "Blender" / "blender-5.1.0-linux-x64" / "blender"
    _fake_blender(blender, version="5.1.0")

    assert find_compatible_blenders(tmp_path / "install") == [blender]


# --- install_base ------------------------------------------------------


def _install_dir_with_extension(tmp_path: Path) -> Path:
    install_dir = tmp_path / "install"
    extension_dir = install_dir / "extension"
    extension_dir.mkdir(parents=True)
    (extension_dir / "posecap.zip").write_bytes(b"fixture")
    return install_dir


def test_install_base_installs_into_a_discovered_blender(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _install_dir_with_extension(tmp_path)
    blender = tmp_path / "bin" / "blender"
    _fake_blender(blender)
    _prepend_to_path(monkeypatch, blender.parent)

    install_base(install_dir)  # must not raise

    assert (blender.parent / "posecap-installed.txt").is_file()


def test_install_base_removes_a_previous_install_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _install_dir_with_extension(tmp_path)
    blender = tmp_path / "bin" / "blender"
    _fake_blender(blender)
    (blender.parent / "posecap-installed.txt").write_text("stale")
    _prepend_to_path(monkeypatch, blender.parent)

    install_base(install_dir)  # remove-then-install must still leave it installed

    assert (blender.parent / "posecap-installed.txt").read_text() == "installed"


def test_install_base_raises_when_the_extension_zip_is_missing(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    install_dir.mkdir()

    with pytest.raises(BaseInstallError, match="extension package is missing"):
        install_base(install_dir)


def test_install_base_raises_when_no_blender_is_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _install_dir_with_extension(tmp_path)
    _prepend_to_path(monkeypatch, tmp_path / "empty")

    with pytest.raises(BaseInstallError, match="Blender 4.2 or newer was not found"):
        install_base(install_dir)


def test_install_base_raises_when_blender_rejects_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _install_dir_with_extension(tmp_path)
    blender = tmp_path / "bin" / "blender"
    _fake_blender(blender, fail_commands=True)
    _prepend_to_path(monkeypatch, blender.parent)

    with pytest.raises(BaseInstallError):
        install_base(install_dir)


# --- component_lifecycle ----------------------------------------------


def test_full_lifecycle_produces_a_ready_inventory(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    component_lifecycle.begin(install_dir, "base,mediapipe", "1.0.0")
    component_lifecycle.base_ready(install_dir)
    backend_manifest = install_dir / "backends" / "mediapipe" / "backend.json"
    backend_manifest.parent.mkdir(parents=True)
    backend_manifest.write_text("{}")

    component_lifecycle.complete(install_dir, "base,mediapipe")

    inventory = json.loads((install_dir / "installed_components.json").read_text())
    assert inventory["transaction_state"] == "ready"
    assert "previous_version" not in inventory
    assert inventory["components"]["base"]["state"] == "ready"
    assert inventory["components"]["mediapipe"]["state"] == "ready"
    assert inventory["components"]["mediapipe"]["manifest"]["state"] == "registered"


def test_invalid_component_selection_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(component_lifecycle.ComponentLifecycleError):
        component_lifecycle.begin(tmp_path / "install", "base,mhr", "1.0.0")


def test_malformed_inventory_schema_is_rejected(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    (install_dir / "installed_components.json").write_text(json.dumps({"schema_version": 99}))

    with pytest.raises(component_lifecycle.ComponentLifecycleError, match="unsupported schema"):
        component_lifecycle.read_installed_inventory(install_dir)


def test_deselecting_mediapipe_removes_its_owned_paths(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    component_lifecycle.begin(install_dir, "base,mediapipe", "1.0.0")
    backend_dir = install_dir / "backends" / "mediapipe"
    backend_dir.mkdir(parents=True)
    (backend_dir / "backend.json").write_text("{}")
    (install_dir / "payloads" / "mediapipe").mkdir(parents=True)
    component_lifecycle.base_ready(install_dir)
    component_lifecycle.complete(install_dir, "base,mediapipe")

    component_lifecycle.begin(install_dir, "base", "1.0.1")

    assert not (install_dir / "backends" / "mediapipe").exists()
    assert not (install_dir / "payloads" / "mediapipe").exists()


def test_remove_owned_tree_refuses_to_escape_the_install_root(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    install_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("do not delete me")

    with pytest.raises(component_lifecycle.ComponentLifecycleError, match="refusing to remove"):
        component_lifecycle._remove_installer_owned_tree(install_dir, "../outside.txt")
    assert outside.is_file()


# --- install_mediapipe ---------------------------------------------------


def test_install_mediapipe_registers_a_schema_valid_backend_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = tmp_path / "install"
    _mediapipe_payload(install_dir / "payloads" / "mediapipe")
    (install_dir / "backends" / "mediapipe" / "models").mkdir(parents=True)
    model_bytes = b"fixture"
    (install_dir / "backends" / "mediapipe" / "models" / "holistic_landmarker.task").write_bytes(
        model_bytes
    )
    monkeypatch.setattr(
        build_mediapipe_payload_linux, "_MODEL_SHA256", hashlib.sha256(model_bytes).hexdigest()
    )

    install_mediapipe(install_dir)

    manifest_path = install_dir / "backends" / "mediapipe" / "backend.json"
    manifest = decode_pose_backend_manifest(manifest_path.read_text(encoding="utf-8"))
    assert manifest.id == "mediapipe"
    assert "linux" in manifest.compatibility.operating_systems
    assert manifest.command[0].endswith("posecap-mediapipe")
    assert (install_dir / "backends" / "mediapipe" / "runtime" / "bin" / "python").is_file()


def test_install_mediapipe_raises_when_the_model_checksum_does_not_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = tmp_path / "install"
    _mediapipe_payload(install_dir / "payloads" / "mediapipe")
    (install_dir / "backends" / "mediapipe" / "models").mkdir(parents=True)
    (install_dir / "backends" / "mediapipe" / "models" / "holistic_landmarker.task").write_bytes(
        b"corrupted-download"
    )
    monkeypatch.setattr(
        build_mediapipe_payload_linux,
        "_MODEL_SHA256",
        hashlib.sha256(b"the-real-model").hexdigest(),
    )

    with pytest.raises(MediaPipeInstallError, match="does not match its pinned checksum"):
        install_mediapipe(install_dir)


def test_install_mediapipe_raises_when_the_payload_is_incomplete(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    (install_dir / "payloads" / "mediapipe").mkdir(parents=True)

    with pytest.raises(MediaPipeInstallError, match="required component file is missing"):
        install_mediapipe(install_dir)


def test_install_mediapipe_skips_reinstall_when_repair_finds_a_healthy_runtime(
    tmp_path: Path,
) -> None:
    install_dir = tmp_path / "install"
    backend_dir = install_dir / "backends" / "mediapipe"
    launcher = backend_dir / "runtime" / "bin" / "posecap-mediapipe"
    model_path = backend_dir / "models" / "holistic_landmarker.task"
    manifest_path = backend_dir / "backend.json"
    _write_executable(launcher, "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_bytes(b"fixture")
    manifest_path.write_text("{}")
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "installed_components.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "version": "1.0.0",
                "transaction_state": "installing",
                "previous_version": "1.0.0",
                "components": {},
            }
        )
    )
    # No payload directory at all -- if install proceeded past the repair
    # shortcut it would fail on the missing payload.

    install_mediapipe(install_dir)  # must not raise


# --- bootstrap_install -----------------------------------------------


def _prepare_bootstrap_install_dir(tmp_path: Path) -> Path:
    install_dir = _install_dir_with_extension(tmp_path)
    (install_dir / "installer_manifest.json").write_text(json.dumps({"version": "1.2.3"}))
    return install_dir


def test_bootstrap_install_runs_base_and_mediapipe_then_marks_setup_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _prepare_bootstrap_install_dir(tmp_path)
    calls: list[str] = []

    def fake_install_base(target: Path) -> None:
        calls.append("base")
        assert target == install_dir

    def fake_install_mediapipe(target: Path) -> None:
        calls.append("mediapipe")
        backend_dir = target / "backends" / "mediapipe"
        backend_dir.mkdir(parents=True)
        (backend_dir / "backend.json").write_text("{}")

    monkeypatch.setattr(bootstrap_install_module, "install_base", fake_install_base)
    monkeypatch.setattr(bootstrap_install_module, "install_mediapipe", fake_install_mediapipe)

    exit_code = bootstrap_install_module.bootstrap_install(install_dir, "base,mediapipe")

    assert exit_code == 0
    assert calls == ["base", "mediapipe"]
    assert (install_dir / "logs" / "SETUP_OK").is_file()
    inventory = json.loads((install_dir / "installed_components.json").read_text())
    assert inventory["transaction_state"] == "ready"


def test_bootstrap_install_fails_cleanly_when_base_install_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _prepare_bootstrap_install_dir(tmp_path)

    def failing_install_base(_target: Path) -> None:
        raise BaseInstallError("Blender 4.2 or newer was not found")

    monkeypatch.setattr(bootstrap_install_module, "install_base", failing_install_base)

    exit_code = bootstrap_install_module.bootstrap_install(install_dir, "base")

    assert exit_code == 1
    assert not (install_dir / "logs" / "SETUP_OK").exists()


def test_bootstrap_install_requires_an_installer_manifest(tmp_path: Path) -> None:
    install_dir = _install_dir_with_extension(tmp_path)

    exit_code = bootstrap_install_module.bootstrap_install(install_dir, "base")

    assert exit_code == 1


# --- nvidia_detect -----------------------------------------------------


def _fake_nvidia_smi(path: Path, *, healthy: bool = True) -> None:
    exit_code = "0" if healthy else "1"
    _write_executable(path, f"#!/usr/bin/env python3\nimport sys\nsys.exit({exit_code})\n")


def test_nvidia_driver_present_true_when_nvidia_smi_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nvidia_smi = tmp_path / "bin" / "nvidia-smi"
    _fake_nvidia_smi(nvidia_smi, healthy=True)
    _prepend_to_path(monkeypatch, nvidia_smi.parent)

    assert nvidia_driver_present() is True


def test_nvidia_driver_present_false_when_nvidia_smi_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nvidia_smi = tmp_path / "bin" / "nvidia-smi"
    _fake_nvidia_smi(nvidia_smi, healthy=False)
    _prepend_to_path(monkeypatch, nvidia_smi.parent)

    assert nvidia_driver_present() is False


def test_nvidia_driver_present_false_when_nvidia_smi_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    assert nvidia_driver_present() is False


# --- component_lifecycle: PEAR ------------------------------------------


def test_full_lifecycle_with_pear_produces_a_ready_inventory(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    component_lifecycle.begin(install_dir, "base,mediapipe,pear", "1.0.0")
    component_lifecycle.base_ready(install_dir)
    for name in ("mediapipe", "pear"):
        backend_manifest = install_dir / "backends" / name / "backend.json"
        backend_manifest.parent.mkdir(parents=True)
        backend_manifest.write_text("{}")

    component_lifecycle.complete(install_dir, "base,mediapipe,pear")

    inventory = json.loads((install_dir / "installed_components.json").read_text())
    assert inventory["components"]["pear"]["state"] == "ready"
    assert inventory["components"]["pear"]["manifest"]["state"] == "registered"
    assert inventory["components"]["pear"]["retained_data_paths"] == ["pear"]


def test_deselecting_pear_retains_source_but_removes_runtime(tmp_path: Path) -> None:
    install_dir = tmp_path / "install"
    component_lifecycle.begin(install_dir, "base,pear", "1.0.0")
    backend_dir = install_dir / "backends" / "pear"
    backend_dir.mkdir(parents=True)
    (backend_dir / "backend.json").write_text("{}")
    (install_dir / "runtime").mkdir(parents=True)
    (install_dir / "pear").mkdir(parents=True)
    (install_dir / "pear" / "configs.yaml").write_text("user-acquired data")
    component_lifecycle.base_ready(install_dir)
    component_lifecycle.complete(install_dir, "base,pear")

    component_lifecycle.begin(install_dir, "base", "1.0.1")

    assert not (install_dir / "backends" / "pear").exists()
    assert not (install_dir / "runtime").exists()
    assert (install_dir / "pear" / "configs.yaml").is_file()


# --- install_pear --------------------------------------------------------


_FAKE_PEAR_PYTHON = """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
if args[:1] == ["-c"]:
    Path("yolov8s.pt").write_bytes(b"fixture")
    sys.exit(0)
if args[:3] == ["-m", "posecap_engine.cli", "doctor"]:
    scenario = os.environ.get("FAKE_DOCTOR_SCENARIO", "ok")
    if scenario == "ok":
        print(json.dumps({"ok": True, "pear_root": None, "checks": []}))
        sys.exit(0)
    if scenario == "pear_assets_only":
        print(json.dumps({
            "ok": False, "pear_root": None,
            "checks": [{"name": "pear_assets", "status": "error", "message": "missing",
                        "details": {}}],
        }))
        sys.exit(1)
    print(json.dumps({
        "ok": False, "pear_root": None,
        "checks": [{"name": "torch_cuda", "status": "error", "message": "no cuda",
                    "details": {}}],
    }))
    sys.exit(1)
sys.exit(2)
"""

_FAKE_PEAR_UV = """#!/usr/bin/env python3
import sys
from pathlib import Path

FAKE_PYTHON = __FAKE_PYTHON_SOURCE__

args = sys.argv[1:]
if args[:2] == ["python", "install"]:
    sys.exit(0)
if args and args[0] == "venv":
    bin_dir = Path(args[-1], "bin")
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_path = bin_dir / "python"
    python_path.write_text(FAKE_PYTHON)
    python_path.chmod(0o755)
    sys.exit(0)
if args[:2] == ["pip", "install"]:
    sys.exit(0)
sys.exit(0)
""".replace("__FAKE_PYTHON_SOURCE__", repr(_FAKE_PEAR_PYTHON))


def _fake_pear_uv(path: Path) -> None:
    _write_executable(path, _FAKE_PEAR_UV)


def _fake_pear_source_archive(path: Path, *, revision_hint: str = "pear-src") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{revision_hint}/models/__init__.py", b"")
        archive.writestr(f"{revision_hint}/utils/__init__.py", b"")
        archive.writestr(f"{revision_hint}/configs/infer.yaml", b"config: true\n")


def _pear_install_dir(tmp_path: Path, *, wheel_count: int = 4) -> Path:
    install_dir = tmp_path / "install"
    _fake_pear_uv(install_dir / "bin" / "uv")
    (install_dir / "wheels").mkdir(parents=True)
    for index in range(wheel_count):
        (install_dir / "wheels" / f"pkg{index}-1.0.0-py3-none-any.whl").write_bytes(b"fixture")
    (install_dir / "requirements-torch.lock").write_text("torch==2.9.1+cu128\n")
    (install_dir / "requirements-pypi.lock").write_text("ultralytics==8.4.80\n")
    (install_dir / "installer_manifest.json").write_text(
        json.dumps(
            {
                "version": "1.0.7",
                "torchIndexUrl": "https://download.pytorch.org/whl/cu128",
                "pearRevision": "977331937ea8c3d08ae0254d8831d640d46a5cf6",
            }
        )
    )
    _fake_pear_source_archive(install_dir / "payloads" / "pear" / "pear-source.zip")
    return install_dir


def test_fetch_pear_source_merges_into_an_existing_checkout_with_licensed_assets(
    tmp_path: Path,
) -> None:
    # Real bug found in the field: a prior checkout (e.g. from an earlier
    # manual setup) already has a non-empty assets/ directory holding the
    # user's own downloaded licensed SMPL-X/FLAME/MANO files. A GitHub
    # archive zip extracts to "PEAR-<revision>/", a different top-level name
    # than "pear/" -- the old code tried to `rename()` the fresh assets/
    # directory over the existing non-empty one and crashed with ENOTEMPTY.
    pear_dir = tmp_path / "pear"
    pear_dir.mkdir()
    licensed_asset = pear_dir / "assets" / "SMPL" / "SMPL_NEUTRAL.pkl"
    licensed_asset.parent.mkdir(parents=True)
    licensed_asset.write_bytes(b"the user's own licensed model, never touch this")
    # A pre-existing (older) source file that a fresh checkout should update.
    (pear_dir / "configs").mkdir()
    (pear_dir / "configs" / "infer.yaml").write_text("config: old\n")

    source_archive = tmp_path / "pear-source.zip"
    _fake_pear_source_archive(
        source_archive, revision_hint="PEAR-977331937ea8c3d08ae0254d8831d640d46a5cf6"
    )

    _fetch_pear_source(
        source_archive, pear_dir, "977331937ea8c3d08ae0254d8831d640d46a5cf6"
    )  # must not raise

    assert licensed_asset.read_bytes() == b"the user's own licensed model, never touch this"
    assert (pear_dir / "configs" / "infer.yaml").read_text() == "config: true\n"
    assert (pear_dir / "models" / "__init__.py").is_file()
    assert (
        pear_dir / ".posecap-source-revision"
    ).read_text() == "977331937ea8c3d08ae0254d8831d640d46a5cf6"


def test_install_pear_raises_without_an_nvidia_driver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _pear_install_dir(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    with pytest.raises(PearInstallError, match="no NVIDIA driver"):
        install_pear(install_dir)


def test_install_pear_tolerates_a_licensed_assets_only_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _pear_install_dir(tmp_path)
    nvidia_smi = tmp_path / "gpu-bin" / "nvidia-smi"
    _fake_nvidia_smi(nvidia_smi, healthy=True)
    _prepend_to_path(monkeypatch, nvidia_smi.parent)
    monkeypatch.setenv("FAKE_DOCTOR_SCENARIO", "pear_assets_only")

    install_pear(install_dir)  # must not raise

    manifest_path = install_dir / "backends" / "pear" / "backend.json"
    manifest = decode_pose_backend_manifest(manifest_path.read_text(encoding="utf-8"))
    assert manifest.id == "pear"
    assert manifest.compatibility.operating_systems == ("linux",)
    assert manifest.compatibility.accelerators == ("nvidia-cuda",)
    assert manifest.capabilities == ("body", "hands", "face")
    assert (install_dir / "pear" / "model_zoo" / "yolov8s.pt").is_file()
    assert (install_dir / "pear" / ".posecap-source-revision").read_text() == (
        "977331937ea8c3d08ae0254d8831d640d46a5cf6"
    )


def test_install_pear_raises_on_a_non_licensing_doctor_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _pear_install_dir(tmp_path)
    nvidia_smi = tmp_path / "gpu-bin" / "nvidia-smi"
    _fake_nvidia_smi(nvidia_smi, healthy=True)
    _prepend_to_path(monkeypatch, nvidia_smi.parent)
    monkeypatch.setenv("FAKE_DOCTOR_SCENARIO", "other_error")

    with pytest.raises(PearInstallError, match="doctor reported failing checks"):
        install_pear(install_dir)


def test_install_pear_raises_when_the_source_archive_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _pear_install_dir(tmp_path)
    (install_dir / "payloads" / "pear" / "pear-source.zip").unlink()
    nvidia_smi = tmp_path / "gpu-bin" / "nvidia-smi"
    _fake_nvidia_smi(nvidia_smi, healthy=True)
    _prepend_to_path(monkeypatch, nvidia_smi.parent)

    with pytest.raises(PearInstallError, match="PEAR source archive not found"):
        install_pear(install_dir)


# --- bootstrap_install: default selection + PEAR wiring -----------------


def test_default_components_includes_pear_when_nvidia_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap_install_module, "nvidia_driver_present", lambda: True)

    assert bootstrap_install_module._default_components() == "base,mediapipe,pear"


def test_default_components_excludes_pear_without_nvidia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bootstrap_install_module, "nvidia_driver_present", lambda: False)

    assert bootstrap_install_module._default_components() == "base,mediapipe"


def test_bootstrap_install_runs_pear_when_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_dir = _prepare_bootstrap_install_dir(tmp_path)
    calls: list[str] = []

    def fake_install_base(target: Path) -> None:
        calls.append("base")

    def fake_install_pear(target: Path) -> None:
        calls.append("pear")
        backend_dir = target / "backends" / "pear"
        backend_dir.mkdir(parents=True)
        (backend_dir / "backend.json").write_text("{}")

    monkeypatch.setattr(bootstrap_install_module, "install_base", fake_install_base)
    monkeypatch.setattr(bootstrap_install_module, "install_pear", fake_install_pear)

    exit_code = bootstrap_install_module.bootstrap_install(install_dir, "base,pear")

    assert exit_code == 0
    assert calls == ["base", "pear"]
    inventory = json.loads((install_dir / "installed_components.json").read_text())
    assert inventory["components"]["pear"]["state"] == "ready"
