from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from posecap_addon.support import (
    addon_version,
    create_support_bundle,
    default_installation_paths,
    diagnostic_summary,
    resolve_logs_directory,
)


def test_addon_version_reads_the_installer_build_label(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "posecap_addon"
    package.mkdir()
    (tmp_path / "blender_manifest.toml").write_text('version = "2.3.4"\n', encoding="utf-8")
    local_app_data = tmp_path / "LocalAppData"
    install_root = local_app_data / "PoseCap"
    install_root.mkdir(parents=True)
    (install_root / "installer_manifest.json").write_text(
        '{"version": "2.3.4-win.7"}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    assert addon_version(package / "support.py") == "2.3.4-win.7"


def test_addon_version_falls_back_for_a_manual_extension_install(
    tmp_path: Path, monkeypatch
) -> None:
    package = tmp_path / "posecap_addon"
    package.mkdir()
    (tmp_path / "blender_manifest.toml").write_text('version = "2.3.4"\n', encoding="utf-8")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)

    assert addon_version(package / "support.py") == "2.3.4"


def test_default_installation_paths_use_the_fixed_per_user_layout() -> None:
    paths = default_installation_paths({"LOCALAPPDATA": "C:/Users/Ale/AppData/Local"})

    assert paths is not None
    assert paths.pear_root == Path("C:/Users/Ale/AppData/Local/PoseCap/pear")
    assert paths.engine_executable == Path(
        "C:/Users/Ale/AppData/Local/PoseCap/runtime/venv/Scripts/posecap-engine.exe"
    )
    assert paths.backend_registry == Path("C:/Users/Ale/AppData/Local/PoseCap/backends")
    assert paths.logs == Path("C:/Users/Ale/AppData/Local/PoseCap/logs")


def test_logs_follow_a_custom_pear_installation() -> None:
    preferences = SimpleNamespace(
        pear_root="D:/Apps/PoseCap/pear",
        engine_executable="D:/Apps/PoseCap/runtime/venv/Scripts/posecap-engine.exe",
    )

    assert resolve_logs_directory(preferences, {}) == Path("D:/Apps/PoseCap/logs")


def test_support_bundle_contains_diagnostics_and_logs(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "posecap-addon.log").write_text("addon line", encoding="utf-8")
    (logs / "posecap-engine.log.1").write_text("engine line", encoding="utf-8")

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    assert bundle.name == "PoseCap-Support-20260713-123000.zip"
    with zipfile.ZipFile(bundle) as archive:
        assert set(archive.namelist()) == {
            "diagnostics.txt",
            "logs/posecap-addon.log",
            "logs/posecap-engine.log.1",
        }
        assert archive.read("diagnostics.txt") == b"PoseCap version: 1.0.0\n"


def test_diagnostics_report_readiness_without_secrets(tmp_path: Path) -> None:
    pear = tmp_path / "pear"
    engine = tmp_path / "posecap-engine.exe"
    pear.mkdir()
    engine.write_bytes(b"")

    report = diagnostic_summary(
        version="1.0.0",
        blender_version="5.0.1",
        lifecycle_state="STOPPED",
        pear_root=str(pear),
        engine_executable=str(engine),
        logs_directory=tmp_path / "logs",
    )

    assert "PEAR root exists: True" in report
    assert "Engine executable exists: True" in report
    assert "password" not in report.lower()
