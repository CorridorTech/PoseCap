"""Render the online Windows installer from one verified PEAR payload manifest."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--payload-manifest", type=Path, required=True)
    parser.add_argument("--mediapipe-payload-manifest", type=Path, required=True)
    parser.add_argument("--staging", type=Path, required=True)
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--base-version", required=True)
    parser.add_argument("--output-basename", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def render_installer(arguments: argparse.Namespace) -> None:
    manifest: dict[str, Any] = json.loads(arguments.payload_manifest.read_text(encoding="utf-8"))
    archive = _validated_archive(manifest, expected_version=arguments.app_version)
    pear_source = _validated_pear_source(manifest)
    mediapipe_manifest: dict[str, Any] = json.loads(
        arguments.mediapipe_payload_manifest.read_text(encoding="utf-8")
    )
    mediapipe_archive, mediapipe_model = _validated_mediapipe_payload(
        mediapipe_manifest, expected_version=arguments.app_version
    )
    replacements = {
        "@@APP_VERSION@@": arguments.app_version,
        "@@BASE_VERSION@@": arguments.base_version,
        "@@DISPLAY_LABEL@@": arguments.app_version,
        "@@OUTPUT_BASENAME@@": arguments.output_basename,
        "@@STAGING@@": str(arguments.staging),
        "@@PEAR_PAYLOAD_URL@@": archive["url"],
        "@@PEAR_PAYLOAD_FILENAME@@": archive["filename"],
        "@@PEAR_PAYLOAD_SHA256@@": archive["sha256"],
        "@@PEAR_PAYLOAD_INSTALLED_SIZE@@": str(archive["installed_size_bytes"]),
        "@@PEAR_SOURCE_URL@@": pear_source["url"],
        "@@PEAR_SOURCE_FILENAME@@": pear_source["filename"],
        "@@PEAR_SOURCE_SHA256@@": pear_source["sha256"],
        "@@PEAR_SOURCE_SIZE@@": str(pear_source["size_bytes"]),
        "@@MEDIAPIPE_PAYLOAD_URL@@": mediapipe_archive["url"],
        "@@MEDIAPIPE_PAYLOAD_FILENAME@@": mediapipe_archive["filename"],
        "@@MEDIAPIPE_PAYLOAD_SHA256@@": mediapipe_archive["sha256"],
        "@@MEDIAPIPE_PAYLOAD_INSTALLED_SIZE@@": str(mediapipe_archive["installed_size_bytes"]),
        "@@MEDIAPIPE_MODEL_URL@@": mediapipe_model["url"],
        "@@MEDIAPIPE_MODEL_SHA256@@": mediapipe_model["sha256"],
        "@@MEDIAPIPE_MODEL_SIZE@@": str(mediapipe_model["size_bytes"]),
    }
    rendered = arguments.template.read_text(encoding="utf-8")
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    if re.search(r"@@[A-Z_]+@@", rendered):
        raise ValueError("installer template contains an unrendered token")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")


def _validated_archive(manifest: dict[str, Any], *, expected_version: str) -> dict[str, Any]:
    if manifest.get("schema_version") != 1 or isinstance(manifest.get("schema_version"), bool):
        raise ValueError("schema_version must be 1")
    if manifest.get("component") != "pear":
        raise ValueError("component must be pear")
    if manifest.get("version") != expected_version:
        raise ValueError(f"version must match installer version {expected_version}")
    archive = manifest.get("archive")
    if not isinstance(archive, dict):
        raise ValueError("archive must be an object")

    filename = archive.get("filename")
    if (
        not isinstance(filename, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.zip", filename) is None
    ):
        raise ValueError("archive.filename must be a safe zip basename")
    url = archive.get("url")
    if not isinstance(url, str):
        raise ValueError("archive.url must be an HTTPS URL")
    parsed_url = urlparse(url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or any(character in url for character in ('"', "\r", "\n"))
    ):
        raise ValueError("archive.url must be an HTTPS URL")
    sha256 = archive.get("sha256")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-fA-F]{64}", sha256) is None:
        raise ValueError("archive.sha256 must be 64 hexadecimal characters")
    for size_field in ("size_bytes", "installed_size_bytes"):
        size = archive.get(size_field)
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise ValueError(f"archive.{size_field} must be a positive integer")
    return archive


def _validated_pear_source(manifest: dict[str, Any]) -> dict[str, Any]:
    pear_source = manifest.get("pear_source")
    if not isinstance(pear_source, dict):
        raise ValueError("pear_source must be an object")
    if pear_source.get("filename") != "pear-source.zip":
        raise ValueError("pear_source.filename must be pear-source.zip")
    url = pear_source.get("url")
    if not isinstance(url, str):
        raise ValueError("pear_source.url must be an HTTPS URL")
    parsed_url = urlparse(url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or any(character in url for character in ('"', "\r", "\n"))
    ):
        raise ValueError("pear_source.url must be an HTTPS URL")
    sha256 = pear_source.get("sha256")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-fA-F]{64}", sha256) is None:
        raise ValueError("pear_source.sha256 must be 64 hexadecimal characters")
    size = pear_source.get("size_bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError("pear_source.size_bytes must be a positive integer")
    return pear_source


def _validated_mediapipe_payload(
    manifest: dict[str, Any], *, expected_version: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    if manifest.get("schema_version") != 1 or isinstance(manifest.get("schema_version"), bool):
        raise ValueError("schema_version must be 1")
    if manifest.get("component") != "mediapipe":
        raise ValueError("component must be mediapipe")
    if manifest.get("version") != expected_version:
        raise ValueError(f"version must match installer version {expected_version}")
    archive = _validated_download(manifest.get("archive"), label="archive", zip_name=True)
    installed_size = archive.get("installed_size_bytes")
    if isinstance(installed_size, bool) or not isinstance(installed_size, int):
        raise ValueError("archive.installed_size_bytes must be a positive integer")
    if installed_size < 1:
        raise ValueError("archive.installed_size_bytes must be a positive integer")
    model = _validated_download(manifest.get("model"), label="model", zip_name=False)
    if model["filename"] != "holistic_landmarker.task":
        raise ValueError("model.filename must be holistic_landmarker.task")
    return archive, model


def _validated_download(value: object, *, label: str, zip_name: bool) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    document = value
    filename = document.get("filename")
    suffix = r"\.zip" if zip_name else r"\.task"
    if (
        not isinstance(filename, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*" + suffix, filename) is None
    ):
        expected_suffix = "zip" if zip_name else "task"
        raise ValueError(f"{label}.filename must be a safe {expected_suffix} basename")
    url = document.get("url")
    if not isinstance(url, str):
        raise ValueError(f"{label}.url must be an HTTPS URL")
    parsed_url = urlparse(url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or any(character in url for character in ('"', "\r", "\n"))
    ):
        raise ValueError(f"{label}.url must be an HTTPS URL")
    sha256 = document.get("sha256")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-fA-F]{64}", sha256) is None:
        raise ValueError(f"{label}.sha256 must be 64 hexadecimal characters")
    size = document.get("size_bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size < 1:
        raise ValueError(f"{label}.size_bytes must be a positive integer")
    return document


def main() -> int:
    try:
        render_installer(_arguments())
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"invalid PEAR payload manifest: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
