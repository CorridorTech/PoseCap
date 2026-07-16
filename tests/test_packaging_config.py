"""Guards for the installer packaging inputs (task 0006).

The installer's determinism rests on these files: the lockfiles must pin the
exact validated runtime matrix (ADR-0007) and the Inno template must keep every
token the renderer replaces. A drifted pin here means a clean machine installs
something the workstation never validated.
"""

import re
from pathlib import Path

_PACKAGING = Path(__file__).parents[1] / "packaging"


def _read(name: str) -> str:
    return (_PACKAGING / name).read_text(encoding="utf-8")


def test_torch_lock_pins_validated_cuda_matrix() -> None:
    lock = _read("requirements-torch.lock")
    assert "torch==2.4.1+cu124" in lock
    assert "torchvision==0.19.1+cu124" in lock


def test_pypi_lock_pins_every_line_exactly() -> None:
    lines = [
        line
        for line in _read("requirements-pypi.lock").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert len(lines) > 50
    for line in lines:
        assert re.fullmatch(r"[A-Za-z0-9._-]+==[A-Za-z0-9.+!]+", line), line
    assert not any(line.startswith("torch==") or line.startswith("torchvision==") for line in lines)
    assert not any("posecap" in line for line in lines)
    assert not any("pytorch3d" in line for line in lines)


def test_iss_template_is_ascii_only() -> None:
    # A non-ASCII char (an em-dash) in the template is read by PowerShell 5.1
    # Get-Content as the ANSI codepage and baked into the compiled installer as
    # mojibake ("â€"). The renderer reads it as UTF-8, but keeping the template
    # ASCII-only is the belt-and-suspenders guard so it can never reappear.
    template = _read("installer/posecap.iss.template")
    non_ascii = sorted({character for character in template if ord(character) > 127})
    assert non_ascii == [], f"non-ASCII characters in the Inno template: {non_ascii}"


def test_installer_build_reads_template_as_utf8() -> None:
    # The renderer must decode the template as UTF-8; the ANSI default silently
    # corrupts any non-ASCII an author later adds.
    renderer = (Path(__file__).parents[1] / "tools" / "render_windows_installer.py").read_text(
        encoding="utf-8"
    )
    assert 'arguments.template.read_text(encoding="utf-8")' in renderer


def test_iss_template_tokens_match_renderer() -> None:
    template = _read("installer/posecap.iss.template")
    tokens = set(re.findall(r"@@([A-Z_]+)@@", template))
    renderer = (Path(__file__).parents[1] / "tools" / "render_windows_installer.py").read_text(
        encoding="utf-8"
    )
    rendered_tokens = set(re.findall(r'"@@([A-Z_]+)@@"', renderer))
    assert tokens == rendered_tokens, (
        f"token drift: template={sorted(tokens)} renderer={sorted(rendered_tokens)}"
    )


def test_installer_uses_one_fixed_per_user_location() -> None:
    template = _read("installer/posecap.iss.template")
    assert "DefaultDirName={localappdata}\\PoseCap" in template
    assert "DisableDirPage=yes" in template


def test_per_user_installer_allows_uv_to_traverse_user_owned_paths() -> None:
    template = _read("installer/posecap.iss.template")

    assert "PrivilegesRequired=lowest" in template
    assert "RedirectionGuard=no" in template


def test_installer_removes_versioned_payload_from_previous_releases() -> None:
    template = _read("installer/posecap.iss.template")

    assert "[InstallDelete]" in template
    assert 'Type: files; Name: "{app}\\wheels\\*.whl"' in template
    assert 'Type: files; Name: "{app}\\extension\\*.zip"' in template


def test_installer_propagates_bootstrap_failure_to_its_exit_code() -> None:
    template = _read("installer/posecap.iss.template")

    assert "[Run]" not in template
    assert "[Code]" in template
    assert "ewWaitUntilTerminated" in template
    assert "ResultCode <> 0" in template
    assert "RaiseException" in template


def test_base_handler_requires_and_verifies_the_blender_extension() -> None:
    base = _read("installer/install_base.ps1")
    assert "Blender 4.2 or newer was not found" in base
    assert "extension install-file -r user_default -e" in base
    assert '@("--command", "extension", "list")' in base
    assert "posecap\\s+\\[installed\\]" in base
    assert "best effort" not in base.lower()


def test_base_handler_replaces_a_stale_blender_extension_before_installing() -> None:
    base = _read("installer/install_base.ps1")

    assert "if ($installedExtensions -match '(?m)^\\s*posecap\\s+\\[installed\\]')" in base
    assert base.index('@("--command", "extension", "remove", "posecap")') < base.index(
        "extension install-file -r user_default -e"
    )


def test_base_handler_selects_the_newest_supported_blender() -> None:
    discovery = _read("installer/blender_discovery.ps1")

    assert "--version" in discovery
    assert "[version]'4.2'" in discovery
    assert "Sort-Object Version -Descending" in discovery


def test_pear_handler_preserves_healthy_repair_or_recreates_runtime() -> None:
    pear = _read("installer/install_pear.ps1")

    health_index = pear.index("if ($sameVersionRepair -and (Test-PearDoctorAcceptsRuntime))")
    recreate_index = pear.index('Invoke-Uv @("venv", "--clear", "--python", "3.11", $VenvDir)')
    assert health_index < recreate_index


def test_pear_handler_never_downloads_licensed_models() -> None:
    pear = _read("installer/install_pear.ps1").lower()
    download_lines = [
        line
        for line in pear.splitlines()
        if "invoke-webrequest" in line or "curl" in line or "hf_hub_download" in line
    ]
    for line in download_lines:
        assert "smpl" not in line and "flame" not in line, line
    # Instruction text must exist so the user knows the manual step.
    assert "smpl-x" in pear
    assert "cannot ship with posecap" in pear


def test_pear_handler_consumes_the_inno_verified_local_source_archive() -> None:
    pear = _read("installer/install_pear.ps1")

    assert '$PearSourceArchive = Join-Path $InstallDir "payloads\\pear\\pear-source.zip"' in pear
    assert "Invoke-WebRequest" not in pear
    assert "Expand-Archive -LiteralPath $PearSourceArchive" in pear
    assert (
        'Set-Content -LiteralPath (Join-Path $PearDir ".posecap-source-revision") '
        "-Value $Manifest.pearRevision -NoNewline" in pear
    )


def test_pear_handler_refreshes_changed_source_without_deleting_retained_data() -> None:
    pear = _read("installer/install_pear.ps1")

    assert "$installedRevision -eq [string]$Manifest.pearRevision" in pear
    assert "Get-ChildItem -LiteralPath $inner.FullName -Force |" in pear
    assert "Copy-Item -Destination $PearDir -Recurse -Force" in pear
    assert "Remove-Item -Recurse -Force -LiteralPath $PearDir" not in pear


def test_pear_handler_registers_backend_only_after_runtime_install() -> None:
    pear = _read("installer/install_pear.ps1")

    doctor_index = pear.index("Verify install (doctor) and fetch pose-model weights")
    engine_index = pear.index('$EnginePath = Join-Path $VenvDir "Scripts\\posecap-engine.exe"')
    assert engine_index > doctor_index
    assert "schema_version = 1" in pear
    assert 'id = "pear"' in pear
    assert 'command = @($EnginePath, "live", "--pear-root", $PearDir)' in pear
    assert "protocol_versions = @(1)" in pear
    assert 'capabilities = @("body", "hands", "face")' in pear
    assert 'operating_systems = @("windows")' in pear
    assert 'accelerators = @("nvidia-cuda")' in pear
    assert 'account = "MPI account required for model downloads"' in pear
    assert "ConvertTo-Json -Depth 4" in pear
    assert "Move-Item -Force" in pear
