import importlib.util
import tomllib
import zipfile
from pathlib import Path

import pytest


def _load_build_extension_module():
    module_path = Path(__file__).parents[2] / "tools" / "build_extension.py"
    spec = importlib.util.spec_from_file_location("build_extension", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_extension_zip_contains_manifest_entrypoint_and_vendored_wheels(
    tmp_path: Path,
) -> None:
    build_extension = _load_build_extension_module()
    repo_root = Path(__file__).parents[2]
    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> None:
        commands.append(command)
        package = command[command.index("--package") + 1]
        output_dir = Path(command[command.index("--out-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        wheel_name = package.replace("-", "_") + "-0.1.0-py3-none-any.whl"
        (output_dir / wheel_name).write_bytes(b"wheel")

    zip_path = build_extension.build_extension(
        repo_root=repo_root,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
        runner=fake_runner,
    )

    assert zip_path == tmp_path / "dist" / "posecap-0.1.0.zip"
    assert [command[:4] for command in commands] == [
        ["uv", "build", "--wheel", "--package"],
        ["uv", "build", "--wheel", "--package"],
    ]

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        manifest = tomllib.loads(archive.read("blender_manifest.toml").decode("utf-8"))

    assert manifest["id"] == "posecap"
    assert manifest["type"] == "add-on"
    assert manifest["license"] == ["SPDX:GPL-3.0-only"]
    assert manifest["wheels"] == [
        "./wheels/posecap_contracts-0.1.0-py3-none-any.whl",
        "./wheels/posecap_core-0.1.0-py3-none-any.whl",
    ]
    assert ".posecap-extension-stage" not in names
    assert "__init__.py" in names
    assert "posecap_addon/__init__.py" in names
    assert "posecap_addon/apply_timer.py" in names
    assert "posecap_addon/engine_process.py" in names
    assert "posecap_addon/instrumentation.py" in names
    assert "posecap_addon/panels.py" in names
    assert "posecap_addon/stream_client.py" in names
    assert "posecap_addon/ui_state.py" in names
    assert "wheels/posecap_contracts-0.1.0-py3-none-any.whl" in names
    assert "wheels/posecap_core-0.1.0-py3-none-any.whl" in names


def test_build_extension_builds_workspace_packages_from_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    build_extension = _load_build_extension_module()
    repo_root = Path(__file__).parents[2]
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    monkeypatch.chdir(outside_cwd)

    def fake_runner(command: list[str]) -> None:
        assert Path.cwd() == repo_root
        package = command[command.index("--package") + 1]
        output_dir = Path(command[command.index("--out-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        wheel_name = package.replace("-", "_") + "-0.1.0-py3-none-any.whl"
        (output_dir / wheel_name).write_bytes(b"wheel")

    build_extension.build_extension(
        repo_root=repo_root,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
        runner=fake_runner,
    )


def test_build_extension_rejects_staging_inside_source_tree(tmp_path: Path) -> None:
    build_extension = _load_build_extension_module()
    repo_root = Path(__file__).parents[2]
    source_file = repo_root / "addon" / "posecap_addon" / "__init__.py"

    with pytest.raises(ValueError, match="staging_dir must not be inside"):
        build_extension.build_extension(
            repo_root=repo_root,
            output_dir=tmp_path / "dist",
            staging_dir=source_file.parent,
            runner=lambda _command: None,
        )

    assert source_file.is_file()


def test_build_extension_rejects_existing_non_stage_directory(tmp_path: Path) -> None:
    build_extension = _load_build_extension_module()
    repo_root = Path(__file__).parents[2]
    important_dir = tmp_path / "important"
    important_dir.mkdir()
    important_file = important_dir / "keep.txt"
    important_file.write_text("do not delete", encoding="utf-8")

    with pytest.raises(ValueError, match="not a PoseCap extension staging directory"):
        build_extension.build_extension(
            repo_root=repo_root,
            output_dir=tmp_path / "dist",
            staging_dir=important_dir,
            runner=lambda _command: None,
        )

    assert important_file.read_text(encoding="utf-8") == "do not delete"
