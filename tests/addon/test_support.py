from __future__ import annotations

import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from posecap_addon.support import (
    MAX_LOG_BYTES,
    MAX_LOG_FILES,
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


def test_support_bundle_caps_the_number_of_log_files(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    for index in range(MAX_LOG_FILES + 2):
        (logs / f"stray-{index:02d}.log").write_text("stray line", encoding="utf-8")

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    with zipfile.ZipFile(bundle) as archive:
        log_entries = [name for name in archive.namelist() if name.startswith("logs/")]
        assert len(log_entries) == MAX_LOG_FILES
        report = archive.read("diagnostics.txt").decode("utf-8")
        assert "Log files omitted from this bundle: 2" in report


def test_support_bundle_caps_the_total_log_bytes(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    over_half_the_budget = MAX_LOG_BYTES // 2 + 1
    base_moment = 1_700_000_000
    (logs / "alpha.log").write_bytes(b"a" * over_half_the_budget)
    (logs / "bravo.log").write_bytes(b"b" * over_half_the_budget)
    (logs / "charlie.log").write_text("small line", encoding="utf-8")
    os.utime(logs / "alpha.log", (base_moment + 3, base_moment + 3))
    os.utime(logs / "bravo.log", (base_moment + 2, base_moment + 2))
    os.utime(logs / "charlie.log", (base_moment + 1, base_moment + 1))

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "logs/alpha.log" in names
        assert "logs/bravo.log" not in names
        assert "logs/charlie.log" in names
        report = archive.read("diagnostics.txt").decode("utf-8")
        assert "Log files omitted from this bundle: 1" in report


def test_setup_marker_counts_toward_the_bundle_caps(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    for index in range(MAX_LOG_FILES):
        (logs / f"stray-{index:02d}.log").write_text("stray line", encoding="utf-8")
    (logs / "SETUP_OK").write_text("ok", encoding="utf-8")

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    with zipfile.ZipFile(bundle) as archive:
        log_entries = [name for name in archive.namelist() if name.startswith("logs/")]
        assert "logs/SETUP_OK" in log_entries
        assert len(log_entries) == MAX_LOG_FILES
        report = archive.read("diagnostics.txt").decode("utf-8")
        assert "Log files omitted from this bundle: 1" in report


def test_the_freshest_logs_across_families_survive_the_caps(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    base_moment = 1_700_000_000
    for index in range(MAX_LOG_FILES):
        stale = logs / f"alpha-{index:02d}.log"
        stale.write_text("older family line", encoding="utf-8")
        os.utime(stale, (base_moment + index, base_moment + index))
    fresh = logs / "zulu.log"
    fresh.write_text("newest family line", encoding="utf-8")
    os.utime(fresh, (base_moment + 1000, base_moment + 1000))

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "logs/zulu.log" in names
        assert "logs/alpha-00.log" not in names
        assert f"logs/alpha-{MAX_LOG_FILES - 1:02d}.log" in names
        report = archive.read("diagnostics.txt").decode("utf-8")
        assert "Log files omitted from this bundle: 1" in report


def test_support_bundle_survives_a_log_vanishing_mid_collection(
    tmp_path: Path, monkeypatch
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "alpha.log").write_text("kept line", encoding="utf-8")
    (logs / "bravo.log").write_text("vanishing line", encoding="utf-8")
    real_write = zipfile.ZipFile.write

    def racing_write(
        archive: zipfile.ZipFile, filename: str | Path, arcname: str | None = None
    ) -> None:
        if Path(filename).name == "bravo.log":
            raise FileNotFoundError(filename)
        real_write(archive, filename, arcname)

    monkeypatch.setattr(zipfile.ZipFile, "write", racing_write)

    bundle = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="PoseCap version: 1.0.0\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "logs/alpha.log" in names
        assert "logs/bravo.log" not in names
        report = archive.read("diagnostics.txt").decode("utf-8")
        assert "Log files omitted from this bundle: 1" in report


def test_same_second_bundle_requests_receive_distinct_names(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    moment = datetime(2026, 7, 13, 12, 30, tzinfo=UTC)

    first = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="first request\n",
        timestamp=moment,
    )
    second = create_support_bundle(
        destination_directory=tmp_path / "Downloads",
        logs_directory=logs,
        diagnostics="second request\n",
        timestamp=moment,
    )

    assert first.name == "PoseCap-Support-20260713-123000.zip"
    assert second.name == "PoseCap-Support-20260713-123000-1.zip"
    assert first.is_file()
    assert second.is_file()


def test_an_existing_bundle_is_never_overwritten(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    existing = downloads / "PoseCap-Support-20260713-123000.zip"
    existing.write_bytes(b"earlier capture evidence")

    bundle = create_support_bundle(
        destination_directory=downloads,
        logs_directory=logs,
        diagnostics="new request\n",
        timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
    )

    assert bundle != existing
    assert existing.read_bytes() == b"earlier capture evidence"
    with zipfile.ZipFile(bundle) as archive:
        assert archive.read("diagnostics.txt") == b"new request\n"


def test_disk_failure_during_log_collection_fails_the_bundle_cleanly(
    tmp_path: Path, monkeypatch
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "alpha.log").write_text("addon line", encoding="utf-8")
    downloads = tmp_path / "Downloads"

    def failing_write(
        archive: zipfile.ZipFile, filename: str | Path, arcname: str | None = None
    ) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(zipfile.ZipFile, "write", failing_write)

    with pytest.raises(OSError):
        create_support_bundle(
            destination_directory=downloads,
            logs_directory=logs,
            diagnostics="doomed request\n",
            timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
        )

    assert list(downloads.glob("*.zip")) == []


def test_a_failed_bundle_attempt_leaves_no_broken_bundle_behind(
    tmp_path: Path, monkeypatch
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    downloads = tmp_path / "Downloads"

    def failing_writestr(archive: zipfile.ZipFile, arcname: str, data: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "writestr", failing_writestr)

    with pytest.raises(OSError):
        create_support_bundle(
            destination_directory=downloads,
            logs_directory=logs,
            diagnostics="doomed request\n",
            timestamp=datetime(2026, 7, 13, 12, 30, tzinfo=UTC),
        )

    assert list(downloads.glob("*.zip")) == []


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
