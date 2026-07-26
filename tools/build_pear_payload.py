"""Package the staged PEAR bootstrap and emit its immutable download manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse

_FORBIDDEN_BINARY_EXTENSIONS = {".npz", ".pkl", ".pt", ".ckpt", ".onnx", ".engine"}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--pear-source-url", required=True)
    parser.add_argument("--pear-source-sha256", required=True)
    parser.add_argument("--pear-source-size", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def build_payload(arguments: argparse.Namespace) -> None:
    base_url = arguments.base_url.rstrip("/")
    parsed_base_url = urlparse(base_url)
    if parsed_base_url.scheme != "https" or not parsed_base_url.netloc:
        raise ValueError("base URL must use HTTPS")
    pear_source_url = arguments.pear_source_url
    parsed_pear_source_url = urlparse(pear_source_url)
    if parsed_pear_source_url.scheme != "https" or not parsed_pear_source_url.netloc:
        raise ValueError("PEAR source URL must use HTTPS")
    pear_source_sha256 = arguments.pear_source_sha256.lower()
    if len(pear_source_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in pear_source_sha256
    ):
        raise ValueError("PEAR source SHA-256 must contain 64 hexadecimal characters")
    if arguments.pear_source_size < 1:
        raise ValueError("PEAR source size must be positive")

    source = arguments.source.resolve()
    uv_relative_path = _uv_relative_path(source)
    required_paths = (
        uv_relative_path,
        "requirements-torch.lock",
        "requirements-pypi.lock",
    )
    for relative_path in required_paths:
        if not (source / relative_path).is_file():
            raise ValueError(f"missing required PEAR payload path: {relative_path}")
    wheels = tuple((source / "wheels").glob("*.whl"))
    if len(wheels) < 4:
        raise ValueError("PEAR payload requires at least four wheels")
    for wheel_path in wheels:
        with zipfile.ZipFile(wheel_path) as wheel:
            for member in wheel.infolist():
                if Path(member.filename).suffix.lower() in _FORBIDDEN_BINARY_EXTENSIONS:
                    raise ValueError(
                        f"forbidden binary inside wheel {wheel_path.name}: {member.filename}"
                    )
    files = sorted(path for path in source.rglob("*") if path.is_file())
    required = set(required_paths)
    for path in files:
        relative_path = path.relative_to(source).as_posix()
        if relative_path in required:
            continue
        if path.parent == source / "wheels" and path.suffix == ".whl":
            continue
        raise ValueError(f"unexpected PEAR payload path: {relative_path}")
    filename = f"posecap-pear-bootstrap-{arguments.version}.zip"
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = arguments.output_dir / filename
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())

    manifest = {
        "schema_version": 1,
        "component": "pear",
        "version": arguments.version,
        "archive": {
            "filename": filename,
            "url": f"{base_url}/{filename}",
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "size_bytes": archive_path.stat().st_size,
            "installed_size_bytes": sum(path.stat().st_size for path in files),
        },
        "pear_source": {
            "filename": "pear-source.zip",
            "url": pear_source_url,
            "sha256": pear_source_sha256,
            "size_bytes": arguments.pear_source_size,
        },
    }
    manifest_path = arguments.output_dir / f"posecap-pear-bootstrap-{arguments.version}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _uv_relative_path(source: Path) -> str:
    """The staged uv binary: bin/uv.exe (Windows) or bin/uv (Linux)."""
    if (source / "bin" / "uv.exe").is_file():
        return "bin/uv.exe"
    if (source / "bin" / "uv").is_file():
        return "bin/uv"
    raise ValueError("missing required PEAR payload path: bin/uv(.exe)")


def main() -> int:
    try:
        build_payload(_arguments())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"could not build PEAR payload: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
