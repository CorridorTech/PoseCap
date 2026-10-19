"""Behavioral contracts for the opt-in cu124 PEAR runtime (ADR-0019).

The switch script and the shared selection helper run under Windows
PowerShell 5.1 against a fixture install tree, with a stub nvidia-smi first on
PATH so the reported GPU is chosen by the test, not by the machine.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell contract")

_INSTALLER = Path(__file__).parents[1] / "packaging" / "installer"
_AMPERE = "NVIDIA GeForce RTX 3080, 8.6"
_BLACKWELL = "NVIDIA GeForce RTX 5090, 12.0"
_CU128_INDEX = "https://download.pytorch.org/whl/cu128"


def _stub_nvidia_smi(tmp_path: Path, gpus: list[str]) -> dict[str, str]:
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    (stub_dir / "gpus.csv").write_text("\n".join(gpus) + "\n", encoding="ascii")
    (stub_dir / "nvidia-smi.cmd").write_text(
        '@echo off\r\ntype "%~dp0gpus.csv"\r\n', encoding="ascii"
    )
    return {**os.environ, "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}


def _install_fixture(tmp_path: Path, *, with_cu124: bool = True) -> Path:
    install_dir = tmp_path / "PoseCap"
    bootstrap = install_dir / "bootstrap"
    bootstrap.mkdir(parents=True)
    for script in ("native_command.ps1", "pear_runtime.ps1", "switch_pear_runtime.ps1"):
        shutil.copyfile(_INSTALLER / script, bootstrap / script)
    # Stand-in for the real handler: records which runtime it was asked to
    # build, and fails on demand so the rollback path can be observed.
    (bootstrap / "install_pear.ps1").write_text(
        "param([string]$InstallDir)\n"
        ". (Join-Path $PSScriptRoot 'native_command.ps1')\n"
        ". (Join-Path $PSScriptRoot 'pear_runtime.ps1')\n"
        "$runtime = Get-PearRuntimeSelection -InstallDir $InstallDir\n"
        "Set-Content (Join-Path $InstallDir 'INSTALL_SAW') $runtime\n"
        "if (Test-Path (Join-Path $InstallDir 'FAIL_INSTALL')) { throw 'uv exited with code 2' }\n",
        encoding="utf-8",
    )
    (install_dir / "installer_manifest.json").write_text(
        json.dumps({"version": "1.2.3-win.4", "torchIndexUrl": _CU128_INDEX}), encoding="utf-8"
    )
    backend = install_dir / "backends" / "pear" / "backend.json"
    backend.parent.mkdir(parents=True)
    backend.write_text("{}", encoding="utf-8")
    (install_dir / "requirements-torch.lock").write_text("torch==2.9.1+cu128\n", encoding="utf-8")
    if with_cu124:
        (install_dir / "requirements-torch-cu124.lock").write_text(
            "torch==2.4.1+cu124\n", encoding="utf-8"
        )
        wheel = install_dir / "wheels" / "cu124" / "pytorch3d-0.7.9-cp311-cp311-win_amd64.whl"
        wheel.parent.mkdir(parents=True)
        wheel.write_bytes(b"fixture")
    return install_dir


def _switch(
    install_dir: Path, runtime: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(install_dir / "bootstrap" / "switch_pear_runtime.ps1"),
            "-Runtime",
            runtime,
        ],
        capture_output=True,
        check=False,
        text=True,
        env=env,
    )


def _helper(snippet: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    script = (
        f". '{_INSTALLER / 'native_command.ps1'}'; . '{_INSTALLER / 'pear_runtime.ps1'}'; "
        f"$ErrorActionPreference = 'Stop'; {snippet}"
    )
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        check=False,
        text=True,
        env=env,
    )


def _preference(install_dir: Path) -> str | None:
    path = install_dir / "pear_runtime.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))["runtime"]


def test_switch_to_cu124_persists_the_choice_and_reinstalls(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)

    result = _switch(install_dir, "cu124", _stub_nvidia_smi(tmp_path, [_AMPERE]))

    assert result.returncode == 0, result.stdout + result.stderr
    assert _preference(install_dir) == "cu124"
    assert (install_dir / "INSTALL_SAW").read_text(encoding="utf-8").strip() == "cu124"
    assert list((install_dir / "logs").glob("switch-pear-runtime-*.log"))


def test_switch_refuses_cu124_when_a_blackwell_gpu_is_present(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)

    result = _switch(install_dir, "cu124", _stub_nvidia_smi(tmp_path, [_AMPERE, _BLACKWELL]))

    assert result.returncode == 1
    assert "RTX 5090" in result.stdout
    assert _preference(install_dir) is None
    assert not (install_dir / "INSTALL_SAW").exists()


def test_switch_restores_the_previous_choice_when_the_reinstall_fails(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)
    (install_dir / "FAIL_INSTALL").write_text("", encoding="utf-8")

    result = _switch(install_dir, "cu124", _stub_nvidia_smi(tmp_path, [_AMPERE]))

    assert result.returncode == 1
    assert "uv exited with code 2" in result.stdout
    assert _preference(install_dir) is None


def test_switch_back_to_the_default_clears_the_preference(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)
    env = _stub_nvidia_smi(tmp_path, [_AMPERE])
    assert _switch(install_dir, "cu124", env).returncode == 0

    result = _switch(install_dir, "cu128", env)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _preference(install_dir) is None
    assert (install_dir / "INSTALL_SAW").read_text(encoding="utf-8").strip() == "cu128"


def test_switch_fails_before_changing_anything_when_the_payload_lacks_cu124(
    tmp_path: Path,
) -> None:
    install_dir = _install_fixture(tmp_path, with_cu124=False)

    result = _switch(install_dir, "cu124", _stub_nvidia_smi(tmp_path, [_AMPERE]))

    assert result.returncode == 1
    assert "does not include the CUDA 12.4 runtime" in result.stdout
    assert _preference(install_dir) is None
    assert not (install_dir / "INSTALL_SAW").exists()


def test_switch_requires_an_installed_pear_backend(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)
    (install_dir / "backends" / "pear" / "backend.json").unlink()

    result = _switch(install_dir, "cu124", _stub_nvidia_smi(tmp_path, [_AMPERE]))

    assert result.returncode == 1
    assert "PEAR is not installed" in result.stdout


@pytest.mark.parametrize(
    ("gpus", "expected"),
    [
        ([_AMPERE], ""),
        (["NVIDIA GeForce RTX 4090, 8.9", "NVIDIA GeForce GTX 1080, 6.1"], ""),
        ([_BLACKWELL], "NVIDIA GeForce RTX 5090"),
        (["NVIDIA B200, 10.0", _AMPERE], "NVIDIA B200"),
        (["Failed to initialize NVML: Unknown Error"], ""),
    ],
)
def test_only_blackwell_gpus_block_the_cu124_runtime(gpus: list[str], expected: str) -> None:
    gpu_list = ", ".join(f"'{gpu}'" for gpu in gpus)
    result = _helper(f"(Get-PearLegacyBlockingGpus -SmiOutput @({gpu_list})) -join '|'")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_default_runtime_spec_follows_the_installer_manifest(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)

    result = _helper(
        f"$s = Get-PearRuntimeSpec -InstallDir '{install_dir}' "
        f"-Runtime (Get-PearRuntimeSelection -InstallDir '{install_dir}') "
        f"-DefaultIndexUrl '{_CU128_INDEX}'; "
        "@($s.Runtime, $s.IndexUrl, (Split-Path -Leaf $s.LockPath), [string]$s.Pytorch3dWheel) "
        "-join '|'"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"cu128|{_CU128_INDEX}|requirements-torch.lock|"


def test_cu124_runtime_spec_pairs_the_lock_with_its_pytorch3d_build(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)

    result = _helper(
        f"$s = Get-PearRuntimeSpec -InstallDir '{install_dir}' -Runtime cu124 "
        f"-DefaultIndexUrl '{_CU128_INDEX}'; "
        "@($s.Runtime, $s.IndexUrl, (Split-Path -Leaf $s.LockPath), "
        "(Split-Path -Leaf $s.Pytorch3dWheel)) -join '|'"
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "cu124|https://download.pytorch.org/whl/cu124|requirements-torch-cu124.lock|"
        "pytorch3d-0.7.9-cp311-cp311-win_amd64.whl"
    )


def test_an_unknown_runtime_preference_is_rejected(tmp_path: Path) -> None:
    install_dir = _install_fixture(tmp_path)
    (install_dir / "pear_runtime.json").write_text('{"runtime": "cu999"}', encoding="utf-8")

    result = _helper(f"Get-PearRuntimeSelection -InstallDir '{install_dir}'")

    assert result.returncode != 0
    assert "unknown runtime 'cu999'" in result.stderr


def test_pear_handler_installs_the_selected_runtime_not_a_fixed_lock() -> None:
    pear = (_INSTALLER / "install_pear.ps1").read_text(encoding="utf-8")

    assert '. (Join-Path $PSScriptRoot "pear_runtime.ps1")' in pear
    assert '"--index-url", $RuntimeSpec.IndexUrl' in pear
    assert '"-r", $RuntimeSpec.LockPath' in pear
    assert "$Manifest.torchIndexUrl," not in pear
    assert pear.index('-Label "Select PEAR runtime"') < pear.index(
        '-Label "Install PyTorch CUDA wheels'
    )
    assert "$RuntimeSpec.Pytorch3dWheel" in pear


def test_switch_shortcuts_ship_with_the_pear_component() -> None:
    template = (_INSTALLER / "posecap.iss.template").read_text(encoding="utf-8")

    for runtime in ("cu124", "cu128"):
        assert f'switch_pear_runtime.ps1"" -Runtime {runtime}"' in template
    shortcut_lines = [line for line in template.splitlines() if "switch_pear_runtime" in line]
    assert len(shortcut_lines) == 2
    assert all(line.endswith("Components: pear") for line in shortcut_lines)
    assert 'Type: files; Name: "{app}\\pear_runtime.json"' in template
