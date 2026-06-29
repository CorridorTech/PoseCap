"""Build the PoseCap Blender extension zip."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tomllib
import zipfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

VENDORED_PACKAGES = ("posecap-contracts", "posecap-core")
STAGE_MARKER = ".posecap-extension-stage"
PROTECTED_REPO_DIRS = (
    ".agents",
    ".claude",
    ".git",
    ".github",
    "addon",
    "contracts",
    "core",
    "doc",
    "engine",
    "tests",
    "tools",
)

Runner = Callable[[list[str]], None]


def build_extension(
    *,
    repo_root: Path,
    output_dir: Path,
    staging_dir: Path,
    runner: Runner | None = None,
) -> Path:
    """Build a Blender extension archive with the shared wheels vendored."""
    repo_root = repo_root.resolve()
    addon_dir = repo_root / "addon"
    staging_dir = staging_dir.resolve()
    output_dir = output_dir.resolve()
    runner = _run if runner is None else runner

    _assert_safe_staging_dir(repo_root, staging_dir)
    if not addon_dir.is_dir():
        raise FileNotFoundError(f"addon source directory not found: {addon_dir}")

    _reset_directory(staging_dir)
    _copy_addon_source(addon_dir, staging_dir)

    wheels_dir = staging_dir / "wheels"
    wheels_dir.mkdir()
    with _working_directory(repo_root):
        for package in VENDORED_PACKAGES:
            runner(["uv", "build", "--wheel", "--package", package, "--out-dir", str(wheels_dir)])

    manifest_path = staging_dir / "blender_manifest.toml"
    manifest = _read_manifest(manifest_path)
    _assert_manifest_wheels_exist(staging_dir, manifest)

    extension_id = _manifest_string(manifest, "id")
    extension_version = _manifest_string(manifest, "version")
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{extension_id}-{extension_version}.zip"
    if zip_path.exists():
        zip_path.unlink()
    _write_zip(staging_dir, zip_path)
    return zip_path


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def _reset_directory(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise ValueError(f"staging_dir exists but is not a directory: {path}")
        if any(path.iterdir()) and not _is_extension_staging_directory(path):
            raise ValueError(f"staging_dir is not a PoseCap extension staging directory: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)
    (path / STAGE_MARKER).write_text("", encoding="utf-8")


def _copy_addon_source(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


@contextmanager
def _working_directory(path: Path) -> Iterator[None]:
    original_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_cwd)


def _read_manifest(path: Path) -> dict[str, Any]:
    with path.open("rb") as manifest_file:
        manifest = tomllib.load(manifest_file)
    if not isinstance(manifest, dict):
        raise ValueError(f"manifest did not parse as a table: {path}")
    return manifest


def _manifest_string(manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"blender_manifest.toml field {key!r} must be a non-empty string")
    return value


def _assert_manifest_wheels_exist(staging_dir: Path, manifest: dict[str, Any]) -> None:
    wheels = manifest.get("wheels")
    if not isinstance(wheels, list) or not wheels:
        raise ValueError("blender_manifest.toml must declare the vendored wheels")
    for wheel in wheels:
        if not isinstance(wheel, str):
            raise ValueError("blender_manifest.toml wheel entries must be strings")
        wheel_path = staging_dir / wheel.removeprefix("./")
        if not wheel_path.is_file():
            raise FileNotFoundError(f"declared wheel is missing: {wheel}")


def _write_zip(source_dir: Path, zip_path: Path) -> None:
    files = sorted(
        path for path in source_dir.rglob("*") if path.is_file() and path.name != STAGE_MARKER
    )
    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source_dir).as_posix())


def _assert_safe_staging_dir(repo_root: Path, staging_dir: Path) -> None:
    if staging_dir == repo_root:
        raise ValueError("staging_dir must not be the repository root")
    for name in PROTECTED_REPO_DIRS:
        protected = repo_root / name
        if protected.exists() and (
            staging_dir == protected or staging_dir.is_relative_to(protected)
        ):
            raise ValueError(f"staging_dir must not be inside repository source path: {protected}")


def _is_extension_staging_directory(path: Path) -> bool:
    if (path / STAGE_MARKER).is_file():
        return True
    return all(
        (path / sentinel).exists()
        for sentinel in ("blender_manifest.toml", "__init__.py", "posecap_addon")
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root containing the addon/ directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist"),
        help="Directory that receives the extension zip.",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path("build") / "posecap-extension",
        help="Temporary directory used to assemble the extension package.",
    )
    args = parser.parse_args(argv)

    zip_path = build_extension(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        staging_dir=args.staging_dir,
    )
    print(zip_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
