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
    build = _read("build_installer.ps1")
    assert "posecap.iss.template') -Raw -Encoding UTF8" in build


def test_iss_template_tokens_match_renderer() -> None:
    template = _read("installer/posecap.iss.template")
    tokens = set(re.findall(r"@@([A-Z_]+)@@", template))
    renderer = _read("build_installer.ps1")
    rendered_tokens = set(re.findall(r"'@@([A-Z_]+)@@'", renderer))
    assert tokens == rendered_tokens, (
        f"token drift: template={sorted(tokens)} renderer={sorted(rendered_tokens)}"
    )


def test_installer_uses_one_fixed_per_user_location() -> None:
    template = _read("installer/posecap.iss.template")
    assert "DefaultDirName={localappdata}\\PoseCap" in template
    assert "DisableDirPage=yes" in template


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


def test_bootstrap_requires_and_verifies_the_blender_extension() -> None:
    bootstrap = _read("installer/bootstrap_install.ps1")
    assert "Blender 4.2 or newer was not found" in bootstrap
    assert "extension install-file -r user_default -e" in bootstrap
    assert "extension list" in bootstrap
    assert "posecap\\s+\\[installed\\]" in bootstrap
    assert "best effort" not in bootstrap.lower()


def test_bootstrap_repair_recreates_the_runtime_without_prompting() -> None:
    bootstrap = _read("installer/bootstrap_install.ps1")

    assert 'Invoke-Uv @("venv", "--clear", "--python", "3.11", $VenvDir)' in bootstrap


def test_bootstrap_never_downloads_licensed_models() -> None:
    bootstrap = _read("installer/bootstrap_install.ps1").lower()
    download_lines = [
        line
        for line in bootstrap.splitlines()
        if "invoke-webrequest" in line or "curl" in line or "hf_hub_download" in line
    ]
    for line in download_lines:
        assert "smpl" not in line and "flame" not in line, line
    # Instruction text must exist so the user knows the manual step.
    assert "smpl-x" in bootstrap
    assert "cannot ship with posecap" in bootstrap
