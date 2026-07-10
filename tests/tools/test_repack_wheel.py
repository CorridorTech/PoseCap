import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "tools"))

from repack_wheel import repack_installed_wheel  # noqa: E402


def _installed_distribution(site_packages: Path) -> None:
    package = site_packages / "demo_pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package / "native.pyd").write_bytes(b"\x00binary\x00")
    cache = package / "__pycache__"
    cache.mkdir()
    (cache / "__init__.cpython-311.pyc").write_bytes(b"stale")

    dist_info = site_packages / "demo_pkg-1.2.3.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: demo-pkg\nVersion: 1.2.3\n", encoding="utf-8")
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\nTag: cp311-cp311-win_amd64\n", encoding="utf-8"
    )
    (dist_info / "top_level.txt").write_text("demo_pkg\n", encoding="utf-8")
    (dist_info / "RECORD").write_text("stale,,\n", encoding="utf-8")


def test_repack_produces_named_wheel_with_fresh_record(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    _installed_distribution(site_packages)

    wheel_path = repack_installed_wheel(
        site_packages=site_packages,
        distribution="demo_pkg",
        output_dir=tmp_path / "out",
    )

    assert wheel_path.name == "demo_pkg-1.2.3-cp311-cp311-win_amd64.whl"
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
        assert "demo_pkg/__init__.py" in names
        assert "demo_pkg/native.pyd" in names
        assert "demo_pkg-1.2.3.dist-info/METADATA" in names
        assert "demo_pkg-1.2.3.dist-info/WHEEL" in names
        assert not any("__pycache__" in name for name in names)
        record = archive.read("demo_pkg-1.2.3.dist-info/RECORD").decode()
        assert "stale" not in record
        assert "demo_pkg/__init__.py,sha256=" in record
        assert record.rstrip().endswith("demo_pkg-1.2.3.dist-info/RECORD,,")


def test_repack_missing_distribution_raises(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    with pytest.raises(FileNotFoundError, match="demo_pkg.dist-info not found"):
        repack_installed_wheel(
            site_packages=site_packages,
            distribution="demo_pkg",
            output_dir=tmp_path / "out",
        )
