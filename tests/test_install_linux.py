"""Contract tests for packaging/install_linux.py, the one-command Linux
install pipeline. The heavy sub-steps (payload building, the actual
installer) already have their own dedicated tests; these focus on
install_linux.py's own logic -- default component selection, manifest
writing, download verification -- and the orchestration wiring between
steps, via monkeypatched stage functions rather than re-faking the whole
pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import install_linux as install_linux_module
import pytest
from install_linux import InstallLinuxError, _default_components, install_linux

# --- default component selection -----------------------------------------


def test_default_components_includes_pear_when_nvidia_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(install_linux_module, "nvidia_driver_present", lambda: True)

    assert _default_components() == "base,mediapipe,pear"


def test_default_components_excludes_pear_without_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install_linux_module, "nvidia_driver_present", lambda: False)

    assert _default_components() == "base,mediapipe"


# --- workspace version + manifest -----------------------------------------


def test_workspace_version_reads_the_real_pyproject() -> None:
    version = install_linux_module._workspace_version()

    assert version  # non-empty
    assert version.count(".") >= 1


def test_write_installer_manifest_has_the_fields_install_pear_needs(tmp_path: Path) -> None:
    install_linux_module._write_installer_manifest(tmp_path, "9.9.9")

    manifest = json.loads((tmp_path / "installer_manifest.json").read_text())
    assert manifest["version"] == "9.9.9"
    assert manifest["torchIndexUrl"] == "https://download.pytorch.org/whl/cu128"
    assert manifest["pearRevision"] == "977331937ea8c3d08ae0254d8831d640d46a5cf6"


# --- download verification -------------------------------------------------


def test_download_and_verify_accepts_a_matching_checksum(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"fixture payload")
    import hashlib

    expected = hashlib.sha256(b"fixture payload").hexdigest()
    destination = tmp_path / "downloaded.bin"

    install_linux_module._download_and_verify(source.as_uri(), destination, expected)

    assert destination.read_bytes() == b"fixture payload"


def test_download_and_verify_rejects_a_checksum_mismatch_and_cleans_up(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"fixture payload")
    destination = tmp_path / "downloaded.bin"

    with pytest.raises(InstallLinuxError, match="did not match its pinned checksum"):
        install_linux_module._download_and_verify(source.as_uri(), destination, "0" * 64)

    assert not destination.exists()


# --- orchestration wiring ---------------------------------------------------


def _patch_stages(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        install_linux_module, "_build_extension", lambda *a, **k: calls.append("extension")
    )
    monkeypatch.setattr(
        install_linux_module, "_stage_mediapipe", lambda *a, **k: calls.append("mediapipe")
    )
    monkeypatch.setattr(install_linux_module, "_stage_pear", lambda *a, **k: calls.append("pear"))
    monkeypatch.setattr(
        install_linux_module,
        "_write_installer_manifest",
        lambda *a, **k: calls.append("manifest"),
    )

    def fake_bootstrap_install(install_dir: Path, components: str) -> int:
        calls.append(f"bootstrap:{components}")
        return 0

    monkeypatch.setattr(
        install_linux_module.bootstrap_install, "bootstrap_install", fake_bootstrap_install
    )
    return calls


def test_install_linux_stages_only_mediapipe_when_pear_is_not_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stages(monkeypatch)

    exit_code = install_linux(install_dir=tmp_path, components="base,mediapipe")

    assert exit_code == 0
    assert calls == ["extension", "manifest", "mediapipe", "bootstrap:base,mediapipe"]


def test_install_linux_stages_both_backends_when_both_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stages(monkeypatch)

    exit_code = install_linux(install_dir=tmp_path, components="base,mediapipe,pear")

    assert exit_code == 0
    assert calls == [
        "extension",
        "manifest",
        "mediapipe",
        "pear",
        "bootstrap:base,mediapipe,pear",
    ]


def test_install_linux_uses_nvidia_aware_default_when_components_not_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _patch_stages(monkeypatch)
    monkeypatch.setattr(install_linux_module, "nvidia_driver_present", lambda: False)

    install_linux(install_dir=tmp_path, components=None)

    assert calls == ["extension", "manifest", "mediapipe", "bootstrap:base,mediapipe"]


def test_install_linux_returns_error_exit_code_when_a_stage_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(install_linux_module, "_build_extension", lambda *a, **k: None)
    monkeypatch.setattr(install_linux_module, "_write_installer_manifest", lambda *a, **k: None)

    def failing_stage(*_args: object, **_kwargs: object) -> None:
        raise InstallLinuxError("fixture failure")

    monkeypatch.setattr(install_linux_module, "_stage_mediapipe", failing_stage)

    exit_code = install_linux(install_dir=tmp_path, components="base,mediapipe")

    assert exit_code == 1
