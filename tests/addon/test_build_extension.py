import importlib.util
import io
import tomllib
import zipfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parents[2]
# Single source of truth for the expected version: the manifest itself.
# Hardcoding the version here broke every release bump (2026-07-10).
VERSION = tomllib.loads(
    (_REPO_ROOT / "addon" / "blender_manifest.toml").read_text(encoding="utf-8")
)["version"]


def _load_build_extension_module():
    module_path = _REPO_ROOT / "tools" / "build_extension.py"
    spec = importlib.util.spec_from_file_location("build_extension", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_flat_wheel_runner(commands: list[list[str]]):
    def runner(command: list[str]) -> None:
        commands.append(command)
        package = command[command.index("--package") + 1]
        output_dir = Path(command[command.index("--out-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        wheel_name = package.replace("-", "_") + f"-{VERSION}-py3-none-any.whl"
        (output_dir / wheel_name).write_bytes(b"wheel")

    return runner


def test_build_extension_zip_contains_manifest_entrypoint_and_vendored_wheels(
    tmp_path: Path,
) -> None:
    build_extension = _load_build_extension_module()
    commands: list[list[str]] = []

    zip_path = build_extension.build_extension(
        repo_root=_REPO_ROOT,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
        runner=_fake_flat_wheel_runner(commands),
    )

    assert zip_path == tmp_path / "dist" / f"posecap-{VERSION}.zip"
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
        f"./wheels/posecap_contracts-{VERSION}-py3-none-any.whl",
        f"./wheels/posecap_core-{VERSION}-py3-none-any.whl",
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
    assert f"wheels/posecap_contracts-{VERSION}-py3-none-any.whl" in names
    assert f"wheels/posecap_core-{VERSION}-py3-none-any.whl" in names


def test_build_extension_builds_workspace_packages_from_repo_root(
    monkeypatch,
    tmp_path: Path,
) -> None:
    build_extension = _load_build_extension_module()
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    monkeypatch.chdir(outside_cwd)
    commands: list[list[str]] = []

    def cwd_checking_runner(command: list[str]) -> None:
        assert Path.cwd() == _REPO_ROOT
        _fake_flat_wheel_runner(commands)(command)

    build_extension.build_extension(
        repo_root=_REPO_ROOT,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
        runner=cwd_checking_runner,
    )


def test_build_extension_rejects_staging_inside_source_tree(tmp_path: Path) -> None:
    build_extension = _load_build_extension_module()
    source_file = _REPO_ROOT / "addon" / "posecap_addon" / "__init__.py"

    with pytest.raises(ValueError, match="staging_dir must not be inside"):
        build_extension.build_extension(
            repo_root=_REPO_ROOT,
            output_dir=tmp_path / "dist",
            staging_dir=source_file.parent,
            runner=lambda _command: None,
        )

    assert source_file.is_file()


def test_build_extension_rejects_existing_non_stage_directory(tmp_path: Path) -> None:
    build_extension = _load_build_extension_module()
    important_dir = tmp_path / "important"
    important_dir.mkdir()
    important_file = important_dir / "keep.txt"
    important_file.write_text("do not delete", encoding="utf-8")

    with pytest.raises(ValueError, match="not a PoseCap extension staging directory"):
        build_extension.build_extension(
            repo_root=_REPO_ROOT,
            output_dir=tmp_path / "dist",
            staging_dir=important_dir,
            runner=lambda _command: None,
        )

    assert important_file.read_text(encoding="utf-8") == "do not delete"


def _fake_valid_wheel_runner(commands: list[list[str]]):
    def runner(command: list[str]) -> None:
        commands.append(command)
        package = command[command.index("--package") + 1]
        output_dir = Path(command[command.index("--out-dir") + 1])
        output_dir.mkdir(parents=True, exist_ok=True)
        name = package.replace("-", "_")
        wheel_path = output_dir / f"{name}-{VERSION}-py3-none-any.whl"
        with zipfile.ZipFile(wheel_path, "w") as archive:
            archive.writestr(f"{name}/__init__.py", "VALUE = 1\n")
            archive.writestr(
                f"{name}-{VERSION}.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {package}\nVersion: {VERSION}\n",
            )
            archive.writestr(
                f"{name}-{VERSION}.dist-info/WHEEL",
                "Wheel-Version: 1.0\nTag: py3-none-any\n",
            )
            archive.writestr(f"{name}-{VERSION}.dist-info/RECORD", "")

    return runner


def test_build_extension_stamps_dev_suffix_on_vendored_wheels(tmp_path: Path) -> None:
    build_extension = _load_build_extension_module()
    commands: list[list[str]] = []

    zip_path = build_extension.build_extension(
        repo_root=_REPO_ROOT,
        output_dir=tmp_path / "dist",
        staging_dir=tmp_path / "stage",
        runner=_fake_valid_wheel_runner(commands),
        wheel_version_suffix="dev7",
    )

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        manifest = tomllib.loads(archive.read("blender_manifest.toml").decode("utf-8"))
        core_wheel = archive.read(f"wheels/posecap_core-{VERSION}.dev7-py3-none-any.whl")

    assert f"wheels/posecap_core-{VERSION}.dev7-py3-none-any.whl" in names
    assert f"wheels/posecap_contracts-{VERSION}.dev7-py3-none-any.whl" in names
    assert not any(name.endswith(f"posecap_core-{VERSION}-py3-none-any.whl") for name in names)
    assert manifest["wheels"] == [
        f"./wheels/posecap_contracts-{VERSION}.dev7-py3-none-any.whl",
        f"./wheels/posecap_core-{VERSION}.dev7-py3-none-any.whl",
    ]

    inner = zipfile.ZipFile(io.BytesIO(core_wheel))
    metadata = inner.read(f"posecap_core-{VERSION}.dev7.dist-info/METADATA").decode()
    assert f"Version: {VERSION}.dev7" in metadata
    record = inner.read(f"posecap_core-{VERSION}.dev7.dist-info/RECORD").decode()
    assert "posecap_core/__init__.py,sha256=" in record
