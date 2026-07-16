"""Behavioral contracts for the modular Windows installer (task 0022)."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).parents[1]
_INSTALLER = _ROOT / "packaging" / "installer"


def _read(name: str) -> str:
    return (_INSTALLER / name).read_text(encoding="utf-8")


def _run_lifecycle(
    install_dir: Path,
    action: str,
    components: str = "base",
) -> subprocess.CompletedProcess[str]:
    if sys.platform != "win32":
        pytest.skip("Windows PowerShell installer contract")
    payload_manifest = install_dir / "pear_payload_manifest.json"
    if "pear" in components and action == "Begin" and not payload_manifest.exists():
        install_dir.mkdir(parents=True, exist_ok=True)
        payload_manifest.write_text(json.dumps(_valid_payload_manifest()), encoding="utf-8")
    mediapipe_payload_manifest = install_dir / "mediapipe_payload_manifest.json"
    if "mediapipe" in components and action == "Begin" and not mediapipe_payload_manifest.exists():
        install_dir.mkdir(parents=True, exist_ok=True)
        mediapipe_payload_manifest.write_text(
            json.dumps(_valid_mediapipe_payload_manifest()), encoding="utf-8"
        )
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_INSTALLER / "component_lifecycle.ps1"),
            "-InstallDir",
            str(install_dir),
            "-Action",
            action,
            "-Components",
            components,
            "-Version",
            "1.2.3-win.4",
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _inventory(install_dir: Path) -> dict[str, Any]:
    return json.loads((install_dir / "installed_components.json").read_text(encoding="utf-8"))


def _prepare_bootstrap_fixture(install_dir: Path) -> None:
    bootstrap_dir = install_dir / "bootstrap"
    bootstrap_dir.mkdir(parents=True)
    shutil.copyfile(
        _INSTALLER / "component_lifecycle.ps1",
        bootstrap_dir / "component_lifecycle.ps1",
    )
    (install_dir / "installer_manifest.json").write_text(
        json.dumps({"version": "1.2.3-win.4"}),
        encoding="utf-8",
    )
    (install_dir / "pear_payload_manifest.json").write_text(
        json.dumps(_valid_payload_manifest()),
        encoding="utf-8",
    )
    (install_dir / "mediapipe_payload_manifest.json").write_text(
        json.dumps(_valid_mediapipe_payload_manifest()),
        encoding="utf-8",
    )
    (bootstrap_dir / "install_base.ps1").write_text(
        "param([string]$InstallDir)\nSet-Content (Join-Path $InstallDir 'BASE_CALLED') 'yes'\n",
        encoding="utf-8",
    )
    (bootstrap_dir / "install_pear.ps1").write_text(
        "param([string]$InstallDir)\n"
        "$manifest = Join-Path $InstallDir 'backends\\pear\\backend.json'\n"
        "New-Item -ItemType Directory -Force (Split-Path -Parent $manifest) | Out-Null\n"
        "Set-Content $manifest '{}'\n"
        "Set-Content (Join-Path $InstallDir 'PEAR_CALLED') 'yes'\n",
        encoding="utf-8",
    )
    (bootstrap_dir / "install_mediapipe.ps1").write_text(
        "param([string]$InstallDir)\n"
        "$manifest = Join-Path $InstallDir 'backends\\mediapipe\\backend.json'\n"
        "New-Item -ItemType Directory -Force (Split-Path -Parent $manifest) | Out-Null\n"
        "Set-Content $manifest '{}'\n"
        "Set-Content (Join-Path $InstallDir 'MEDIAPIPE_CALLED') 'yes'\n",
        encoding="utf-8",
    )


def _run_bootstrap(install_dir: Path, components: str) -> subprocess.CompletedProcess[str]:
    if sys.platform != "win32":
        pytest.skip("Windows PowerShell installer contract")
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_INSTALLER / "bootstrap_install.ps1"),
            "-InstallDir",
            str(install_dir),
            "-Components",
            components,
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _iscc_path() -> Path | None:
    if sys.platform != "win32":
        return None
    candidates = (
        Path.home() / "AppData/Local/Programs/Inno Setup 6/ISCC.exe",
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _powershell_path() -> Path:
    return (
        Path(os.environ.get("WINDIR", "C:/Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )


def _compile_blender_stub(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True)
    source = r"""
using System;
using System.IO;

public static class BlenderStub
{
    public static int Main(string[] args)
    {
        if (Environment.GetEnvironmentVariable("POSECAP_STUB_STDERR") != null)
        {
            Console.Error.WriteLine("TBBmalloc: fixture third-party startup warning");
        }

        if (args.Length == 1 && args[0] == "--version")
        {
            Console.WriteLine("Blender 5.2.0");
            return 0;
        }

        string marker = Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory,
            "posecap-installed.txt"
        );
        string command = string.Join(" ", args);
        if (command == "--command extension list")
        {
            if (File.Exists(marker))
            {
                Console.WriteLine("posecap [installed]");
            }
            return 0;
        }
        if (command.Contains("--command extension install-file"))
        {
            File.WriteAllText(marker, "installed");
            return 0;
        }
        if (command == "--command extension remove posecap")
        {
            if (File.Exists(marker))
            {
                File.Delete(marker);
            }
            return 0;
        }

        Console.Error.WriteLine("Unexpected arguments: " + command);
        return 2;
    }
}
"""
    output_path_quoted = str(output_path).replace("'", "''")
    command = (
        "$source = @'\n"
        f"{source}"
        "\n'@\n"
        "Add-Type -TypeDefinition $source -Language CSharp "
        f"-OutputAssembly '{output_path_quoted}' "
        "-OutputType ConsoleApplication"
    )
    result = subprocess.run(
        [
            str(_powershell_path()),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _run_base_handler(
    install_dir: Path,
    program_files_x86: Path,
    stderr_noise: bool = False,
) -> subprocess.CompletedProcess[str]:
    def quote(path: Path) -> str:
        return str(path).replace("'", "''")

    isolated_program_files = install_dir.parent / "Program Files"
    noise_line = "$env:POSECAP_STUB_STDERR = '1'\n" if stderr_noise else ""
    command = (
        "$ErrorActionPreference = 'Stop'\n"
        f"{noise_line}"
        "function Get-ItemProperty {\n"
        "    [CmdletBinding()] param([string]$Path)\n"
        "    return $null\n"
        "}\n"
        f"$env:ProgramFiles = '{quote(isolated_program_files)}'\n"
        f"${{env:ProgramFiles(x86)}} = '{quote(program_files_x86)}'\n"
        "$env:PATH = 'C:\\Windows\\System32;"
        "C:\\Windows\\System32\\WindowsPowerShell\\v1.0'\n"
        f"& '{quote(_INSTALLER / 'install_base.ps1')}' -InstallDir '{quote(install_dir)}'"
    )
    return subprocess.run(
        [
            str(_powershell_path()),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def _run_renderer(
    tmp_path: Path,
    payload_manifest: dict[str, Any],
) -> tuple[subprocess.CompletedProcess[str], Path]:
    manifest_path = tmp_path / "pear-payload-manifest.json"
    manifest_path.write_text(json.dumps(payload_manifest), encoding="utf-8")
    mediapipe_manifest_path = tmp_path / "mediapipe-payload-manifest.json"
    mediapipe_manifest_path.write_text(
        json.dumps(_valid_mediapipe_payload_manifest()), encoding="utf-8"
    )
    output_path = tmp_path / "posecap.iss"
    result = subprocess.run(
        [
            sys.executable,
            str(_ROOT / "tools" / "render_windows_installer.py"),
            "--template",
            str(_INSTALLER / "posecap.iss.template"),
            "--payload-manifest",
            str(manifest_path),
            "--mediapipe-payload-manifest",
            str(mediapipe_manifest_path),
            "--staging",
            str(tmp_path / "staging"),
            "--app-version",
            "1.2.3-win.4",
            "--base-version",
            "1.2.3",
            "--output-basename",
            "PoseCap_Test_Setup",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    return result, output_path


def _valid_payload_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "component": "pear",
        "version": "1.2.3-win.4",
        "archive": {
            "filename": "posecap-pear-bootstrap-1.2.3-win.4.zip",
            "url": (
                "https://github.com/CorridorTech/PoseCap/releases/download/"
                "v1.2.3-win.4/posecap-pear-bootstrap-1.2.3-win.4.zip"
            ),
            "sha256": "a" * 64,
            "size_bytes": 1234,
            "installed_size_bytes": 5678,
        },
        "pear_source": {
            "filename": "pear-source.zip",
            "url": "https://github.com/Pixel-Talk/PEAR/archive/fixture.zip",
            "sha256": "b" * 64,
            "size_bytes": 9012,
        },
    }


def _valid_mediapipe_payload_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "component": "mediapipe",
        "version": "1.2.3-win.4",
        "archive": {
            "filename": "posecap-mediapipe-bootstrap-1.2.3-win.4.zip",
            "url": (
                "https://github.com/CorridorTech/PoseCap/releases/download/"
                "v1.2.3-win.4/posecap-mediapipe-bootstrap-1.2.3-win.4.zip"
            ),
            "sha256": "c" * 64,
            "size_bytes": 2345,
            "installed_size_bytes": 6789,
        },
        "model": {
            "filename": "holistic_landmarker.task",
            "url": "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
            "sha256": "d" * 64,
            "size_bytes": 13683609,
        },
    }


def _run_payload_packer(
    source: Path,
    output_dir: Path,
    base_url: str = "https://github.com/CorridorTech/PoseCap/releases/download/v1.2.3-win.4",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_ROOT / "tools" / "build_pear_payload.py"),
            "--source",
            str(source),
            "--version",
            "1.2.3-win.4",
            "--base-url",
            base_url,
            "--pear-source-url",
            "https://github.com/Pixel-Talk/PEAR/archive/fixture.zip",
            "--pear-source-sha256",
            "b" * 64,
            "--pear-source-size",
            "9012",
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_inno_exposes_fixed_base_and_optional_pose_backends() -> None:
    template = _read("posecap.iss.template")

    assert "AlwaysShowComponentsList=yes" in template
    assert "UsePreviousSetupType=no" in template
    assert "[Types]" in template
    assert 'Name: "recommended"; Description: "Recommended"' in template
    assert 'Name: "custom"; Description: "Custom"; Flags: iscustom' in template
    assert "[Components]" in template
    base_component = (
        'Name: "base"; Description: "PoseCap Base"; Types: recommended custom; Flags: fixed'
    )
    assert base_component in template
    mediapipe_component = (
        'Name: "mediapipe"; Description: "MediaPipe Lite (CPU, no account)"; '
        "Types: recommended custom"
    )
    pear_component = (
        'Name: "pear"; Description: "PEAR (NVIDIA CUDA, licensed models)"; Types: custom'
    )
    assert mediapipe_component in template
    assert pear_component in template


def test_valid_manifest_renders_selected_verified_external_pear_payload(
    tmp_path: Path,
) -> None:
    result, output_path = _run_renderer(tmp_path, _valid_payload_manifest())

    assert result.returncode == 0, result.stderr
    rendered = output_path.read_text(encoding="utf-8")
    assert (
        'Source: "https://github.com/CorridorTech/PoseCap/releases/download/'
        'v1.2.3-win.4/posecap-pear-bootstrap-1.2.3-win.4.zip"' in rendered
    )
    assert 'DestName: "posecap-pear-bootstrap-1.2.3-win.4.zip"' in rendered
    assert "Components: pear" in rendered
    assert f'Hash: "{"a" * 64}"' in rendered
    assert "Flags: external download extractarchive" in rendered
    assert "ExternalSize: 5678" in rendered
    assert 'Source: "https://github.com/Pixel-Talk/PEAR/archive/fixture.zip"' in rendered
    assert 'DestDir: "{app}\\payloads\\pear"; DestName: "pear-source.zip"' in rendered
    assert f'Hash: "{"b" * 64}"' in rendered
    assert "ExternalSize: 9012" in rendered
    assert "Components: mediapipe" in rendered
    assert 'DestDir: "{app}\\backends\\mediapipe\\models"' in rendered
    assert 'DestName: "holistic_landmarker.task"' in rendered
    assert f'Hash: "{"d" * 64}"' in rendered
    assert "@@PEAR_PAYLOAD_" not in rendered


def test_renderer_rejects_payload_manifest_with_invalid_sha256(tmp_path: Path) -> None:
    manifest = _valid_payload_manifest()
    manifest["archive"]["sha256"] = "not-a-sha"

    result, output_path = _run_renderer(tmp_path, manifest)

    assert result.returncode != 0
    assert "archive.sha256 must be 64 hexadecimal characters" in result.stderr
    assert not output_path.exists()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda manifest: manifest.update(schema_version=2), "schema_version must be 1"),
        (lambda manifest: manifest.update(component="mhr"), "component must be pear"),
        (lambda manifest: manifest.update(version="other"), "version must match"),
        (
            lambda manifest: manifest["archive"].update(filename="../payload.zip"),
            "archive.filename must be a safe zip basename",
        ),
        (
            lambda manifest: manifest["archive"].update(url="http://example.test/payload.zip"),
            "archive.url must be an HTTPS URL",
        ),
        (
            lambda manifest: manifest["archive"].update(size_bytes=0),
            "archive.size_bytes must be a positive integer",
        ),
        (
            lambda manifest: manifest["archive"].update(installed_size_bytes=True),
            "archive.installed_size_bytes must be a positive integer",
        ),
        (
            lambda manifest: manifest["pear_source"].update(url="http://example.test/pear.zip"),
            "pear_source.url must be an HTTPS URL",
        ),
        (
            lambda manifest: manifest["pear_source"].update(sha256="not-a-sha"),
            "pear_source.sha256 must be 64 hexadecimal characters",
        ),
    ],
)
def test_renderer_rejects_malformed_payload_metadata(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], object],
    message: str,
) -> None:
    manifest = _valid_payload_manifest()
    mutate(manifest)

    result, output_path = _run_renderer(tmp_path, manifest)

    assert result.returncode != 0
    assert message in result.stderr
    assert not output_path.exists()


def test_payload_packer_emits_complete_archive_and_verified_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    files = {
        "bin/uv.exe": b"uv",
        "wheels/posecap-contracts.whl": b"contracts",
        "wheels/posecap-core.whl": b"core",
        "wheels/posecap-engine.whl": b"engine",
        "wheels/pytorch3d.whl": b"pytorch3d",
        "requirements-torch.lock": b"torch==fixture",
        "requirements-pypi.lock": b"numpy==fixture",
    }
    for relative_path, content in files.items():
        path = source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".whl":
            with zipfile.ZipFile(path, "w") as wheel:
                wheel.writestr("fixture/__init__.py", content)
        else:
            path.write_bytes(content)
    output_dir = tmp_path / "dist"

    result = _run_payload_packer(source, output_dir)

    assert result.returncode == 0, result.stderr
    archive = output_dir / "posecap-pear-bootstrap-1.2.3-win.4.zip"
    manifest_path = output_dir / "posecap-pear-bootstrap-1.2.3-win.4.json"
    assert archive.is_file()
    with zipfile.ZipFile(archive) as payload_zip:
        assert set(payload_zip.namelist()) == set(files)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["component"] == "pear"
    assert manifest["version"] == "1.2.3-win.4"
    assert manifest["archive"]["filename"] == archive.name
    assert manifest["archive"]["url"].endswith(f"/{archive.name}")
    assert manifest["archive"]["size_bytes"] == archive.stat().st_size
    assert manifest["archive"]["installed_size_bytes"] == sum(
        (source / relative_path).stat().st_size for relative_path in files
    )
    assert manifest["archive"]["sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest["pear_source"] == {
        "filename": "pear-source.zip",
        "url": "https://github.com/Pixel-Talk/PEAR/archive/fixture.zip",
        "sha256": "b" * 64,
        "size_bytes": 9012,
    }
    with zipfile.ZipFile(archive) as payload_zip:
        assert "payloads/pear/pear-source.zip" not in payload_zip.namelist()


def test_payload_packer_rejects_incomplete_staging_tree(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "requirements-torch.lock").write_text("fixture", encoding="utf-8")

    result = _run_payload_packer(source, tmp_path / "dist")

    assert result.returncode != 0
    assert "missing required PEAR payload path: bin/uv.exe" in result.stderr
    assert not (tmp_path / "dist" / "posecap-pear-bootstrap-1.2.3-win.4.zip").exists()


def test_payload_packer_rejects_non_https_publication_url(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()

    result = _run_payload_packer(
        source,
        tmp_path / "dist",
        base_url="http://example.test/releases/v1.2.3-win.4",
    )

    assert result.returncode != 0
    assert "base URL must use HTTPS" in result.stderr
    assert not (tmp_path / "dist").exists()


def test_payload_packer_rejects_unexpected_or_licensed_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    required_files = {
        "bin/uv.exe": b"uv",
        "requirements-torch.lock": b"torch",
        "requirements-pypi.lock": b"pypi",
        "wheels/a.whl": b"a",
        "wheels/b.whl": b"b",
        "wheels/c.whl": b"c",
        "wheels/d.whl": b"d",
        "payloads/pear/SMPLX_NEUTRAL.npz": b"licensed fixture",
    }
    for relative_path, content in required_files.items():
        path = source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".whl":
            with zipfile.ZipFile(path, "w") as wheel:
                wheel.writestr("fixture/__init__.py", content)
        else:
            path.write_bytes(content)

    result = _run_payload_packer(source, tmp_path / "dist")

    assert result.returncode != 0
    assert "unexpected PEAR payload path: payloads/pear/SMPLX_NEUTRAL.npz" in result.stderr


def test_payload_packer_rejects_forbidden_binary_hidden_inside_wheel(tmp_path: Path) -> None:
    source = tmp_path / "source"
    for relative_path in (
        "bin/uv.exe",
        "requirements-torch.lock",
        "requirements-pypi.lock",
    ):
        path = source / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
    wheels = source / "wheels"
    wheels.mkdir()
    for name in ("a.whl", "b.whl", "c.whl"):
        with zipfile.ZipFile(wheels / name, "w") as wheel:
            wheel.writestr("fixture/__init__.py", b"")
    with zipfile.ZipFile(wheels / "d.whl", "w") as wheel:
        wheel.writestr("assets/SMPLX_NEUTRAL.pkl", b"licensed fixture")

    result = _run_payload_packer(source, tmp_path / "dist")

    assert result.returncode != 0
    assert "forbidden binary inside wheel d.whl: assets/SMPLX_NEUTRAL.pkl" in result.stderr


def test_rendered_inno_template_compiles_when_iscc_is_available(tmp_path: Path) -> None:
    iscc = _iscc_path()
    if iscc is None:
        pytest.skip("Inno Setup compiler is not installed")

    staging = tmp_path / "staging"
    for directory in ("bin", "wheels", "extension", "bootstrap"):
        (staging / directory).mkdir(parents=True)
    fixture_files = {
        "bin/uv.exe": b"fixture",
        "wheels/posecap-fixture.whl": b"fixture",
        "extension/posecap-fixture.zip": b"fixture",
        "bootstrap/bootstrap_install.ps1": b"# fixture",
        "requirements-torch.lock": b"fixture==1",
        "requirements-pypi.lock": b"fixture==1",
        "installer_manifest.json": b"{}",
        "pear_payload_manifest.json": b"{}",
        "mediapipe_payload_manifest.json": b"{}",
        "LICENSE": b"fixture license",
        "THIRD_PARTY_NOTICES.md": b"fixture notices",
    }
    for relative_path, content in fixture_files.items():
        (staging / relative_path).write_bytes(content)

    render_result, script = _run_renderer(tmp_path, _valid_payload_manifest())
    assert render_result.returncode == 0, render_result.stderr
    output_dir = tmp_path / "output"

    result = subprocess.run(
        [str(iscc), f"/O{output_dir}", str(script)],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "PoseCap_Test_Setup.exe").is_file()


def test_bootstrap_coordinates_independent_component_handlers() -> None:
    bootstrap = _read("bootstrap_install.ps1")
    base = _read("install_base.ps1").lower()
    pear = _read("install_pear.ps1").lower()
    mediapipe = _read("install_mediapipe.ps1").lower()

    assert "component_lifecycle.ps1" in bootstrap
    assert "install_base.ps1" in bootstrap
    assert "install_mediapipe.ps1" in bootstrap
    assert "install_pear.ps1" in bootstrap
    assert 'if ($SelectedComponents -contains "pear")' in bootstrap
    assert 'if ($SelectedComponents -contains "mediapipe")' in bootstrap
    for forbidden in ("nvidia-smi", "cuda", "pear", "torch", "smpl", "flame"):
        assert forbidden not in base
    assert "extension install-file -r user_default -e" in base
    assert "nvidia-smi" in pear
    assert "torch" in pear
    assert "register pear pose backend" in pear
    assert "nvidia-smi" not in mediapipe
    assert "register mediapipe lite pose backend" in mediapipe


@pytest.mark.parametrize("handler", ["install_mediapipe.ps1", "install_pear.ps1"])
def test_app_local_python_install_does_not_touch_global_python_registration(
    handler: str,
) -> None:
    script = _read(handler)

    assert 'Invoke-Uv @("python", "install", "--no-bin", "--no-registry", "3.11")' in script
    assert '"--force"' not in script


def test_build_stages_every_modular_handler() -> None:
    build = (_INSTALLER.parent / "build_installer.ps1").read_text(encoding="utf-8")

    for script in (
        "bootstrap_install.ps1",
        "blender_discovery.ps1",
        "component_lifecycle.ps1",
        "native_command.ps1",
        "install_base.ps1",
        "install_mediapipe.ps1",
        "install_pear.ps1",
        "uninstall_base.ps1",
    ):
        assert f"'{script}'" in build


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer contract")
def test_base_handler_installs_with_blender_from_default_steam_library(
    tmp_path: Path,
) -> None:
    install_dir = tmp_path / "PoseCap"
    extension_dir = install_dir / "extension"
    extension_dir.mkdir(parents=True)
    with zipfile.ZipFile(extension_dir / "posecap.zip", "w") as extension_zip:
        extension_zip.writestr("blender_manifest.toml", 'id = "posecap"')

    program_files_x86 = tmp_path / "Program Files (x86)"
    blender_dir = program_files_x86 / "Steam/steamapps/common/Blender"
    blender = blender_dir / "blender.exe"
    _compile_blender_stub(blender)

    result = _run_base_handler(install_dir, program_files_x86)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (blender_dir / "posecap-installed.txt").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer contract")
def test_base_handler_survives_blender_stderr_noise_under_stop_preference(
    tmp_path: Path,
) -> None:
    install_dir = tmp_path / "PoseCap"
    extension_dir = install_dir / "extension"
    extension_dir.mkdir(parents=True)
    with zipfile.ZipFile(extension_dir / "posecap.zip", "w") as extension_zip:
        extension_zip.writestr("blender_manifest.toml", 'id = "posecap"')

    program_files_x86 = tmp_path / "Program Files (x86)"
    blender_dir = program_files_x86 / "Steam/steamapps/common/Blender"
    _compile_blender_stub(blender_dir / "blender.exe")

    result = _run_base_handler(install_dir, program_files_x86, stderr_noise=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (blender_dir / "posecap-installed.txt").is_file()
    combined = result.stdout + result.stderr
    assert "TBBmalloc: fixture third-party startup warning" in combined


def test_native_stderr_tolerance_is_centralized_in_one_helper() -> None:
    helper = _read("native_command.ps1")

    assert "2>&1" in helper
    for handler in (
        "install_base.ps1",
        "uninstall_base.ps1",
        "blender_discovery.ps1",
        "install_pear.ps1",
    ):
        content = _read(handler)
        assert "2>&1" not in content, f"{handler} redirects native stderr outside the helper"
        assert "Invoke-NativeCommand" in content


@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer contract")
def test_base_handler_installs_with_blender_from_secondary_steam_library(
    tmp_path: Path,
) -> None:
    install_dir = tmp_path / "PoseCap"
    extension_dir = install_dir / "extension"
    extension_dir.mkdir(parents=True)
    with zipfile.ZipFile(extension_dir / "posecap.zip", "w") as extension_zip:
        extension_zip.writestr("blender_manifest.toml", 'id = "posecap"')

    program_files_x86 = tmp_path / "Program Files (x86)"
    steam_apps = program_files_x86 / "Steam/steamapps"
    steam_apps.mkdir(parents=True)
    secondary_library = tmp_path / "SecondarySteamLibrary"
    blender_dir = secondary_library / "steamapps/common/Blender"
    _compile_blender_stub(blender_dir / "blender.exe")
    escaped_library = str(secondary_library).replace("\\", "\\\\")
    (steam_apps / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"1"\n\t{{\n\t\t"path"\t\t"{escaped_library}"\n\t}}\n}}\n',
        encoding="utf-8",
    )

    result = _run_base_handler(install_dir, program_files_x86)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (blender_dir / "posecap-installed.txt").is_file()


def test_inno_uninstaller_removes_blender_extension_before_app_files() -> None:
    template = _read("posecap.iss.template")

    assert "procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);" in template
    assert "if CurUninstallStep <> usUninstall then" in template
    assert "bootstrap\\uninstall_base.ps1" in template
    assert "ewWaitUntilTerminated" in template
    assert 'Type: files; Name: "{app}\\installed_components.json"' in template
    uninstall_base = _read("uninstall_base.ps1")
    assert "$blenders = @(Find-CompatibleBlenders)" in uninstall_base
    assert "foreach ($blender in $blenders)" in uninstall_base


def test_base_only_coordinator_never_invokes_pear(tmp_path: Path) -> None:
    _prepare_bootstrap_fixture(tmp_path)

    result = _run_bootstrap(tmp_path, "base")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "BASE_CALLED").exists()
    assert not (tmp_path / "PEAR_CALLED").exists()
    assert _inventory(tmp_path)["transaction_state"] == "ready"


def test_base_plus_pear_coordinator_invokes_both_handlers(tmp_path: Path) -> None:
    _prepare_bootstrap_fixture(tmp_path)

    result = _run_bootstrap(tmp_path, "base,pear")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "BASE_CALLED").exists()
    assert (tmp_path / "PEAR_CALLED").exists()
    assert set(_inventory(tmp_path)["components"]) == {"base", "pear"}


def test_base_plus_mediapipe_coordinator_invokes_only_the_license_free_backend(
    tmp_path: Path,
) -> None:
    _prepare_bootstrap_fixture(tmp_path)

    result = _run_bootstrap(tmp_path, "base,mediapipe")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "BASE_CALLED").exists()
    assert (tmp_path / "MEDIAPIPE_CALLED").exists()
    assert not (tmp_path / "PEAR_CALLED").exists()
    assert set(_inventory(tmp_path)["components"]) == {"base", "mediapipe"}


def test_lifecycle_records_pinned_mediapipe_model_provenance(tmp_path: Path) -> None:
    result = _run_lifecycle(tmp_path, "Begin", "base,mediapipe")

    assert result.returncode == 0, result.stderr
    payload = _inventory(tmp_path)["components"]["mediapipe"]["payload"]
    assert payload["model"] == {
        "filename": "holistic_landmarker.task",
        "url": "https://storage.googleapis.com/mediapipe-models/holistic_landmarker.task",
        "sha256": "d" * 64,
        "size_bytes": 13683609,
    }


def test_pear_failure_keeps_successful_base_ready_and_failure_observable(
    tmp_path: Path,
) -> None:
    _prepare_bootstrap_fixture(tmp_path)
    (tmp_path / "bootstrap" / "install_pear.ps1").write_text(
        "param([string]$InstallDir)\nthrow 'synthetic PEAR failure'\n",
        encoding="utf-8",
    )

    result = _run_bootstrap(tmp_path, "base,pear")

    assert result.returncode != 0
    assert (tmp_path / "BASE_CALLED").exists()
    inventory = _inventory(tmp_path)
    assert inventory["transaction_state"] == "installing"
    assert inventory["components"]["base"]["state"] == "ready"
    assert inventory["components"]["pear"]["state"] == "installing"


def test_lifecycle_leaves_an_interrupted_install_observable(tmp_path: Path) -> None:
    result = _run_lifecycle(tmp_path, "Begin", "base,pear")

    assert result.returncode == 0, result.stderr
    inventory = _inventory(tmp_path)
    assert inventory["schema_version"] == 1
    assert inventory["transaction_state"] == "installing"
    assert inventory["components"]["base"]["state"] == "installing"
    assert inventory["components"]["pear"]["manifest"]["state"] == "pending"
    assert "previous_version" in inventory


def test_lifecycle_records_exact_pear_payload_provenance(tmp_path: Path) -> None:
    result = _run_lifecycle(tmp_path, "Begin", "base,pear")

    assert result.returncode == 0, result.stderr
    payload = _inventory(tmp_path)["components"]["pear"]["payload"]
    assert payload == {
        "manifest_path": "pear_payload_manifest.json",
        "filename": "posecap-pear-bootstrap-1.2.3-win.4.zip",
        "url": (
            "https://github.com/CorridorTech/PoseCap/releases/download/"
            "v1.2.3-win.4/posecap-pear-bootstrap-1.2.3-win.4.zip"
        ),
        "sha256": "a" * 64,
        "size_bytes": 1234,
    }


def test_lifecycle_publishes_ready_inventory_atomically(tmp_path: Path) -> None:
    begin = _run_lifecycle(tmp_path, "Begin", "base,pear")
    backend_manifest = tmp_path / "backends" / "pear" / "backend.json"
    backend_manifest.parent.mkdir(parents=True)
    backend_manifest.write_text("{}", encoding="utf-8")

    complete = _run_lifecycle(tmp_path, "Complete", "base,pear")

    assert begin.returncode == 0, begin.stderr
    assert complete.returncode == 0, complete.stderr
    inventory = _inventory(tmp_path)
    assert inventory["transaction_state"] == "ready"
    assert inventory["components"]["base"]["state"] == "ready"
    assert inventory["components"]["pear"]["state"] == "ready"
    assert inventory["components"]["pear"]["manifest"]["state"] == "registered"
    assert not (tmp_path / "installed_components.json.tmp").exists()
    serialized = json.dumps(inventory).lower()
    assert "token" not in serialized
    assert "password" not in serialized
    assert "credential" not in serialized


def test_explicit_pear_removal_preserves_base_and_licensed_data(tmp_path: Path) -> None:
    assert _run_lifecycle(tmp_path, "Begin", "base,pear").returncode == 0
    backend_manifest = tmp_path / "backends" / "pear" / "backend.json"
    backend_manifest.parent.mkdir(parents=True)
    backend_manifest.write_text("{}", encoding="utf-8")
    assert _run_lifecycle(tmp_path, "Complete", "base,pear").returncode == 0

    runtime_marker = tmp_path / "runtime" / "venv" / "marker.txt"
    python_marker = tmp_path / "python" / "marker.txt"
    uv_marker = tmp_path / "bin" / "uv.exe"
    wheel_marker = tmp_path / "wheels" / "posecap-engine.whl"
    payload_marker = tmp_path / "payloads" / "pear" / "pear-source.zip"
    licensed_model = tmp_path / "pear" / "assets" / "body_models" / "SMPLX_NEUTRAL.npz"
    base_marker = tmp_path / "extension" / "posecap.zip"
    for marker in (
        runtime_marker,
        python_marker,
        uv_marker,
        wheel_marker,
        payload_marker,
        licensed_model,
        base_marker,
    ):
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("fixture", encoding="utf-8")

    remove = _run_lifecycle(tmp_path, "Begin", "base")
    complete = _run_lifecycle(tmp_path, "Complete", "base")

    assert remove.returncode == 0, remove.stderr
    assert complete.returncode == 0, complete.stderr
    assert not runtime_marker.exists()
    assert not python_marker.exists()
    assert not uv_marker.exists()
    assert not wheel_marker.exists()
    assert not payload_marker.exists()
    assert not backend_manifest.exists()
    assert licensed_model.exists()
    assert base_marker.exists()
    inventory = _inventory(tmp_path)
    assert set(inventory["components"]) == {"base"}


def test_selected_pear_repair_does_not_delete_a_healthy_runtime(tmp_path: Path) -> None:
    assert _run_lifecycle(tmp_path, "Begin", "base,pear").returncode == 0
    backend_manifest = tmp_path / "backends" / "pear" / "backend.json"
    backend_manifest.parent.mkdir(parents=True)
    backend_manifest.write_text("{}", encoding="utf-8")
    assert _run_lifecycle(tmp_path, "Complete", "base,pear").returncode == 0
    runtime_marker = tmp_path / "runtime" / "venv" / "healthy.txt"
    runtime_marker.parent.mkdir(parents=True)
    runtime_marker.write_text("healthy", encoding="utf-8")

    repair = _run_lifecycle(tmp_path, "Begin", "base,pear")

    assert repair.returncode == 0, repair.stderr
    assert runtime_marker.exists()
    assert _inventory(tmp_path)["previous_version"] == "1.2.3-win.4"


def test_legacy_monolithic_layout_is_adopted_without_duplicate_environment(
    tmp_path: Path,
) -> None:
    legacy_runtime = tmp_path / "runtime" / "venv" / "Scripts" / "posecap-engine.exe"
    legacy_manifest = tmp_path / "backends" / "pear" / "backend.json"
    legacy_data = tmp_path / "pear" / "configs" / "infer.yaml"
    for path in (legacy_runtime, legacy_manifest, legacy_data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy", encoding="utf-8")

    begin = _run_lifecycle(tmp_path, "Begin", "base,pear")

    assert begin.returncode == 0, begin.stderr
    assert legacy_runtime.exists()
    assert legacy_manifest.exists()
    assert legacy_data.exists()
    inventory = _inventory(tmp_path)
    assert inventory["previous_version"] is None
    assert inventory["components"]["pear"]["owned_paths"] == [
        "bin",
        "wheels",
        "requirements-torch.lock",
        "requirements-pypi.lock",
        "payloads/pear",
        "python",
        "runtime",
        "backends/pear",
    ]
    assert not (tmp_path / "backends" / "pear" / "runtime").exists()


def test_base_only_upgrade_removes_pre_registry_monolithic_runtime(tmp_path: Path) -> None:
    legacy_runtime = tmp_path / "runtime" / "venv" / "Scripts" / "posecap-engine.exe"
    legacy_python = tmp_path / "python" / "cpython.exe"
    licensed_data = tmp_path / "pear" / "assets" / "body_models" / "SMPLX_NEUTRAL.npz"
    for path in (legacy_runtime, legacy_python, licensed_data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("legacy", encoding="utf-8")

    begin = _run_lifecycle(tmp_path, "Begin", "base")

    assert begin.returncode == 0, begin.stderr
    assert not legacy_runtime.exists()
    assert not legacy_python.exists()
    assert licensed_data.exists()


def test_malformed_inventory_blocks_cleanup_without_deleting_files(tmp_path: Path) -> None:
    inventory_path = tmp_path / "installed_components.json"
    inventory_path.write_text("{not json", encoding="utf-8")
    runtime_marker = tmp_path / "runtime" / "venv" / "keep.txt"
    runtime_marker.parent.mkdir(parents=True)
    runtime_marker.write_text("keep", encoding="utf-8")

    result = _run_lifecycle(tmp_path, "Begin", "base")

    assert result.returncode != 0
    output = " ".join((result.stdout + result.stderr).lower().split())
    assert "malformed installed component inventory" in output
    assert runtime_marker.exists()
    assert inventory_path.read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize("components", ["", "pear", "base,unknown", "base,base"])
def test_lifecycle_rejects_invalid_component_sets(tmp_path: Path, components: str) -> None:
    result = _run_lifecycle(tmp_path, "Begin", components)

    assert result.returncode != 0
    assert not (tmp_path / "installed_components.json").exists()
