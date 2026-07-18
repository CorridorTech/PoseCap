"""Contract tests for packaging/build_pear_payload_linux.py.

Fakes the expensive/network steps (`uv build`) via an injected runner, but
lets tools/repack_wheel.py and tools/build_pear_payload.py run for real
(directly invoking them with sys.executable instead of `uv run`) against a
minimal real PyTorch3D site-packages fixture, so the actual repacked wheel
and archive/manifest output are verified.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from build_pear_payload_linux import PearPayloadBuildError, build_pear_payload_for_linux


def _fake_pytorch3d_site_packages(root: Path) -> Path:
    """A minimal, real site-packages tree repack_wheel.py can process for real."""
    package_dir = root / "pytorch3d"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("__version__ = '0.7.9'\n")
    dist_info = root / "pytorch3d-0.7.9.dist-info"
    dist_info.mkdir()
    (dist_info / "WHEEL").write_text(
        "Wheel-Version: 1.0\nGenerator: fixture\nTag: cp311-cp311-linux_x86_64\n"
    )
    (dist_info / "METADATA").write_text("Metadata-Version: 2.1\nName: pytorch3d\nVersion: 0.7.9\n")
    return root


def _fake_runner():
    def runner(command: Sequence[str]) -> None:
        command = list(command)
        if "build" in command and "--wheel" in command:
            package = command[command.index("--package") + 1]
            out_dir = Path(command[command.index("--out-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            wheel_name = package.replace("-", "_") + "-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(out_dir / wheel_name, "w") as archive:
                archive.writestr("fixture/__init__.py", b"fixture")
            return
        script_index = next(
            (
                i
                for i, part in enumerate(command)
                if part.endswith("repack_wheel.py") or part.endswith("build_pear_payload.py")
            ),
            None,
        )
        if script_index is not None:
            real_command = [sys.executable, *command[script_index:]]
            result = subprocess.run(real_command, capture_output=True, text=True, check=False)
            assert result.returncode == 0, result.stderr
            return
        raise AssertionError(f"unexpected command: {command}")

    return runner


def test_builds_a_linux_pear_payload_with_a_repacked_pytorch3d_wheel(tmp_path: Path) -> None:
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_bytes(b"fixture uv binary")
    site_packages = _fake_pytorch3d_site_packages(tmp_path / "site-packages")
    output_dir = tmp_path / "dist"
    staging_dir = tmp_path / "staging"

    build_pear_payload_for_linux(
        pytorch3d_site_packages=site_packages,
        base_url="https://example.test/releases/v1.0.0-linux.1",
        build_number=1,
        output_dir=output_dir,
        staging_dir=staging_dir,
        runner=_fake_runner(),
        uv_path=fake_uv,
    )

    archives = list(output_dir.glob("posecap-pear-bootstrap-*-linux.1.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        names = set(archive.namelist())
    assert "bin/uv" in names
    assert "bin/uv.exe" not in names
    assert "requirements-torch.lock" in names
    assert "requirements-pypi.lock" in names
    wheel_names = [name for name in names if name.startswith("wheels/")]
    assert len(wheel_names) == 4  # contracts, core, engine, pytorch3d
    assert any("pytorch3d" in name for name in wheel_names)

    manifest_path = next(output_dir.glob("posecap-pear-bootstrap-*-linux.1.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pear_source"]["url"] == (
        "https://github.com/Pixel-Talk/PEAR/archive/977331937ea8c3d08ae0254d8831d640d46a5cf6.zip"
    )


def test_staged_locks_match_the_source_files(tmp_path: Path) -> None:
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_bytes(b"fixture uv binary")
    site_packages = _fake_pytorch3d_site_packages(tmp_path / "site-packages")
    staging_dir = tmp_path / "staging"

    build_pear_payload_for_linux(
        pytorch3d_site_packages=site_packages,
        base_url="https://example.test/releases/v1.0.0-linux.1",
        output_dir=tmp_path / "dist",
        staging_dir=staging_dir,
        runner=_fake_runner(),
        uv_path=fake_uv,
    )

    repo_root = Path(__file__).parents[1]
    assert (staging_dir / "requirements-torch.lock").read_text() == (
        repo_root / "packaging" / "requirements-torch.lock"
    ).read_text()
    assert (staging_dir / "requirements-pypi.lock").read_text() == (
        repo_root / "packaging" / "requirements-pypi-linux.lock"
    ).read_text()


def test_raises_when_pytorch3d_is_not_in_the_given_site_packages(tmp_path: Path) -> None:
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_bytes(b"fixture uv binary")
    empty_site_packages = tmp_path / "site-packages"
    empty_site_packages.mkdir()

    with pytest.raises(PearPayloadBuildError, match="pytorch3d package not found"):
        build_pear_payload_for_linux(
            pytorch3d_site_packages=empty_site_packages,
            base_url="https://example.test/releases/v1.0.0-linux.1",
            output_dir=tmp_path / "dist",
            staging_dir=tmp_path / "staging",
            runner=_fake_runner(),
            uv_path=fake_uv,
        )
