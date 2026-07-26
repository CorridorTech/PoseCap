import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

_ROOT = Path(__file__).parents[1]


def test_mediapipe_payload_is_limited_to_runtime_bootstrap_and_has_pinned_model(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    files = {
        "bin/uv.exe": b"uv",
        "requirements-mediapipe.lock": b"mediapipe==fixture",
        "wheels/posecap-contracts.whl": b"contracts",
        "wheels/posecap-core.whl": b"core",
        "wheels/posecap-engine.whl": b"engine",
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".whl":
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("fixture/__init__.py", content)
        else:
            path.write_bytes(content)
    output = tmp_path / "dist"

    result = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "tools" / "build_mediapipe_payload.py"),
            "--source",
            str(source),
            "--version",
            "1.2.3-win.4",
            "--base-url",
            "https://example.test/releases/v1.2.3-win.4",
            "--model-url",
            "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
            "--model-sha256",
            "a" * 64,
            "--model-size",
            "13683609",
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    archive = output / "posecap-mediapipe-bootstrap-1.2.3-win.4.zip"
    manifest = json.loads(
        (output / "posecap-mediapipe-bootstrap-1.2.3-win.4.json").read_text(encoding="utf-8")
    )
    with zipfile.ZipFile(archive) as payload:
        assert set(payload.namelist()) == set(files)
    assert manifest["component"] == "mediapipe"
    assert manifest["archive"]["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest["model"] == {
        "filename": "holistic_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
        "sha256": "a" * 64,
        "size_bytes": 13683609,
    }


def test_mediapipe_payload_accepts_the_posix_uv_binary_without_an_exe_suffix(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    files = {
        "bin/uv": b"uv",
        "requirements-mediapipe.lock": b"mediapipe==fixture",
        "wheels/posecap-contracts.whl": b"contracts",
        "wheels/posecap-core.whl": b"core",
        "wheels/posecap-engine.whl": b"engine",
    }
    for relative, content in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".whl":
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("fixture/__init__.py", content)
        else:
            path.write_bytes(content)
    output = tmp_path / "dist"

    result = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "tools" / "build_mediapipe_payload.py"),
            "--source",
            str(source),
            "--version",
            "1.2.3-linux.4",
            "--base-url",
            "https://example.test/releases/v1.2.3-linux.4",
            "--model-url",
            "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
            "--model-sha256",
            "a" * 64,
            "--model-size",
            "13683609",
            "--output-dir",
            str(output),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    archive = output / "posecap-mediapipe-bootstrap-1.2.3-linux.4.zip"
    with zipfile.ZipFile(archive) as payload:
        assert set(payload.namelist()) == set(files)


def test_mediapipe_payload_rejects_a_source_missing_both_uv_binaries(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "wheels").mkdir(parents=True)
    (source / "requirements-mediapipe.lock").write_text("mediapipe==fixture")
    for name in ("posecap-contracts", "posecap-core", "posecap-engine"):
        with zipfile.ZipFile(source / "wheels" / f"{name}.whl", "w") as archive:
            archive.writestr("fixture/__init__.py", b"fixture")

    result = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "tools" / "build_mediapipe_payload.py"),
            "--source",
            str(source),
            "--version",
            "1.2.3-linux.4",
            "--base-url",
            "https://example.test/releases/v1.2.3-linux.4",
            "--model-url",
            "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
            "--model-sha256",
            "a" * 64,
            "--model-size",
            "13683609",
            "--output-dir",
            str(tmp_path / "dist"),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert "bin/uv" in result.stderr
