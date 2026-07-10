"""Repack an installed site-packages distribution into a wheel file.

PyTorch3D has no official Windows wheel and building it needs MSVC plus the
CUDA Toolkit — none of which exist on a clean end-user machine. The installer
therefore bundles a wheel repacked from the workstation venv that already
built and validated it (task 0007). RECORD is regenerated with fresh hashes so
the archive is a well-formed wheel, not a bit-copy of install bookkeeping.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import zipfile
from pathlib import Path

_EXCLUDED_DIR = "__pycache__"


def repack_installed_wheel(
    *,
    site_packages: Path,
    distribution: str,
    output_dir: Path,
) -> Path:
    """Zip an installed distribution (package dir + dist-info) into a wheel."""
    dist_info = _find_dist_info(site_packages, distribution)
    wheel_tags = _read_wheel_tags(dist_info)
    version = dist_info.name.removesuffix(".dist-info").split("-", 1)[1]
    wheel_name = f"{distribution}-{version}-{wheel_tags}.whl"

    top_level_names = _read_top_level(dist_info, distribution)
    members: list[Path] = []
    for name in top_level_names:
        package_dir = site_packages / name
        if package_dir.is_dir():
            members.extend(_iter_files(package_dir))
        else:
            module_file = site_packages / f"{name}.py"
            if module_file.is_file():
                members.append(module_file)
    members.extend(path for path in _iter_files(dist_info) if path.name != "RECORD")
    if not members:
        raise FileNotFoundError(f"no files found for distribution {distribution}")

    output_dir.mkdir(parents=True, exist_ok=True)
    wheel_path = output_dir / wheel_name
    record_rows: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(members):
            arcname = path.relative_to(site_packages).as_posix()
            data = path.read_bytes()
            archive.writestr(arcname, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest())
            record_rows.append((arcname, f"sha256={digest.rstrip(b'=').decode()}", str(len(data))))
        record_name = f"{dist_info.name}/RECORD"
        record_rows.append((record_name, "", ""))
        buffer = io.StringIO(newline="")
        csv.writer(buffer, lineterminator="\n").writerows(record_rows)
        archive.writestr(record_name, buffer.getvalue())
    return wheel_path


def _find_dist_info(site_packages: Path, distribution: str) -> Path:
    normalized = distribution.replace("-", "_").lower()
    for candidate in site_packages.glob("*.dist-info"):
        name = candidate.name.removesuffix(".dist-info").split("-", 1)[0]
        if name.lower() == normalized:
            return candidate
    raise FileNotFoundError(f"{distribution}.dist-info not found under {site_packages}")


def _read_wheel_tags(dist_info: Path) -> str:
    for line in (dist_info / "WHEEL").read_text(encoding="utf-8").splitlines():
        if line.startswith("Tag:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"no Tag line in {dist_info / 'WHEEL'}")


def _read_top_level(dist_info: Path, distribution: str) -> list[str]:
    top_level = dist_info / "top_level.txt"
    if top_level.is_file():
        names = [line.strip() for line in top_level.read_text(encoding="utf-8").splitlines()]
        return [name for name in names if name]
    return [distribution.replace("-", "_")]


def _iter_files(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and _EXCLUDED_DIR not in path.relative_to(root.parent).parts
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--distribution", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    wheel_path = repack_installed_wheel(
        site_packages=args.site_packages,
        distribution=args.distribution,
        output_dir=args.output_dir,
    )
    print(wheel_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
