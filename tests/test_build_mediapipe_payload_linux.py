"""Contract tests for packaging/build_mediapipe_payload_linux.py.

Fakes the expensive/network steps (`uv build`, finding a real `uv` binary)
via an injected runner, but lets the final packaging step run for real
(directly invoking tools/build_mediapipe_payload.py with sys.executable
instead of `uv run`) so the actual archive/manifest output is verified.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path

from build_mediapipe_payload_linux import build_mediapipe_payload_for_linux


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
            (i for i, part in enumerate(command) if part.endswith("build_mediapipe_payload.py")),
            None,
        )
        if script_index is not None:
            real_command = [sys.executable, *command[script_index:]]
            result = subprocess.run(real_command, capture_output=True, text=True, check=False)
            assert result.returncode == 0, result.stderr
            return
        raise AssertionError(f"unexpected command: {command}")

    return runner


def test_builds_a_linux_payload_with_the_posix_uv_binary(tmp_path: Path) -> None:
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_bytes(b"fixture uv binary")
    output_dir = tmp_path / "dist"
    staging_dir = tmp_path / "staging"

    build_mediapipe_payload_for_linux(
        base_url="https://example.test/releases/v1.0.0-linux.1",
        build_number=1,
        output_dir=output_dir,
        staging_dir=staging_dir,
        runner=_fake_runner(),
        uv_path=fake_uv,
    )

    archives = list(output_dir.glob("posecap-mediapipe-bootstrap-*-linux.1.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        names = set(archive.namelist())
    assert "bin/uv" in names
    assert "bin/uv.exe" not in names
    assert "requirements-mediapipe.lock" in names
    wheel_names = [name for name in names if name.startswith("wheels/")]
    assert len(wheel_names) == 3


def test_staged_lock_file_matches_the_linux_lock_source(tmp_path: Path) -> None:
    fake_uv = tmp_path / "fake-uv"
    fake_uv.write_bytes(b"fixture uv binary")
    staging_dir = tmp_path / "staging"

    build_mediapipe_payload_for_linux(
        base_url="https://example.test/releases/v1.0.0-linux.1",
        output_dir=tmp_path / "dist",
        staging_dir=staging_dir,
        runner=_fake_runner(),
        uv_path=fake_uv,
    )

    linux_lock = Path(__file__).parents[1] / "packaging" / "requirements-mediapipe-linux.lock"
    staged_lock = staging_dir / "requirements-mediapipe.lock"
    assert staged_lock.read_text() == linux_lock.read_text()
