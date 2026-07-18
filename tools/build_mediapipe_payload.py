"""Package the MediaPipe bootstrap and its immutable publication manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--model-size", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def build_payload(arguments: argparse.Namespace) -> None:
    base_url = _https_url(arguments.base_url.rstrip("/"), "base URL")
    model_url = _https_url(arguments.model_url, "model URL")
    model_sha256 = _sha256(arguments.model_sha256, "model SHA-256")
    if arguments.model_size < 1:
        raise ValueError("model size must be positive")

    source = arguments.source.resolve()
    uv_relative_path = _uv_relative_path(source)
    required_paths = (uv_relative_path, "requirements-mediapipe.lock")
    for relative_path in required_paths:
        if not (source / relative_path).is_file():
            raise ValueError(f"missing required MediaPipe payload path: {relative_path}")
    wheels = tuple((source / "wheels").glob("*.whl"))
    if len(wheels) != 3:
        raise ValueError("MediaPipe payload requires exactly three PoseCap wheels")
    files = sorted(path for path in source.rglob("*") if path.is_file())
    required = set(required_paths)
    for path in files:
        relative_path = path.relative_to(source).as_posix()
        is_wheel = path.parent == source / "wheels" and path.suffix == ".whl"
        if relative_path in required or is_wheel:
            continue
        raise ValueError(f"unexpected MediaPipe payload path: {relative_path}")

    filename = f"posecap-mediapipe-bootstrap-{arguments.version}.zip"
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = arguments.output_dir / filename
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(source).as_posix())

    manifest = {
        "schema_version": 1,
        "component": "mediapipe",
        "version": arguments.version,
        "archive": {
            "filename": filename,
            "url": f"{base_url}/{filename}",
            "sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
            "size_bytes": archive_path.stat().st_size,
            "installed_size_bytes": sum(path.stat().st_size for path in files),
        },
        "model": {
            "filename": "holistic_landmarker.task",
            "url": model_url,
            "sha256": model_sha256,
            "size_bytes": arguments.model_size,
        },
    }
    manifest_path = arguments.output_dir / f"posecap-mediapipe-bootstrap-{arguments.version}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _uv_relative_path(source: Path) -> str:
    """The staged uv binary: bin/uv.exe (Windows) or bin/uv (Linux)."""
    if (source / "bin" / "uv.exe").is_file():
        return "bin/uv.exe"
    if (source / "bin" / "uv").is_file():
        return "bin/uv"
    raise ValueError("missing required MediaPipe payload path: bin/uv(.exe)")


def _https_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError(f"{label} must use HTTPS")
    return value


def _sha256(value: str, label: str) -> str:
    normalized = value.lower()
    is_sha256 = len(normalized) == 64 and all(
        character in "0123456789abcdef" for character in normalized
    )
    if not is_sha256:
        raise ValueError(f"{label} must contain 64 hexadecimal characters")
    return normalized


def main() -> int:
    try:
        build_payload(_arguments())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"could not build MediaPipe payload: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
