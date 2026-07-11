# Build the PoseCap Windows installer (task 0006; CK2P pattern, light flavor).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1 [-BuildNumber 1]
#
# Stages the bundled payload (uv.exe, PoseCap wheels, repacked PyTorch3D wheel,
# Blender extension zip, bootstrap script, pinned lockfiles, manifest), renders
# the Inno Setup template, and compiles the setup exe into packaging\dist.
#
# Requires on the BUILD machine: uv, Inno Setup 6 (ISCC), and the validated
# .venv-pear from tools\install\setup_pear_runtime.ps1 (source of the repacked
# PyTorch3D wheel). End-user machines need none of this.

#Requires -Version 5.1
[CmdletBinding()]
param(
    # 0 is reserved for dev builds; a shipped installer carries a real id.
    [ValidateRange(1, 999999)] [int]$BuildNumber = 1
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
$Dist = Join-Path $ScriptRoot 'dist'
$Staging = Join-Path $ScriptRoot 'work\staging'
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Dist, $Staging | Out-Null

function Invoke-Checked {
    param([string]$Label, [string[]]$Command)
    Write-Host "==> $Label"
    $program = $Command[0]
    $arguments = @()
    if ($Command.Count -gt 1) { $arguments = $Command[1..($Command.Count - 1)] }
    & $program @arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

# --- Version: single source of truth is the root pyproject ---------------------
$pyproject = Get-Content (Join-Path $RepoRoot 'pyproject.toml') -Raw
if ($pyproject -notmatch 'version = "([^"]+)"') { throw 'version not found in pyproject.toml' }
$baseVersion = $Matches[1]
$displayLabel = "$baseVersion-win.$BuildNumber"
Write-Host "==> version: $displayLabel"

# --- Pins: read from the engine config so the manifest can never drift ---------
$configPy = Get-Content (Join-Path $RepoRoot 'engine\src\posecap_engine\config.py') -Raw
if ($configPy -notmatch 'PEAR_REVISION = "([0-9a-f]{40})"') { throw 'PEAR_REVISION not found in engine config' }
$pearRevision = $Matches[1]

# --- Stage bundled payload ------------------------------------------------------
Write-Host '==> staging payload'
New-Item -ItemType Directory -Force -Path `
    (Join-Path $Staging 'bin'), (Join-Path $Staging 'wheels'), `
    (Join-Path $Staging 'extension'), (Join-Path $Staging 'bootstrap') | Out-Null

# uv.exe: the one binary the bootstrap needs; copied from the build machine.
$uvSource = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($null -eq $uvSource) { throw 'uv not found on PATH -- install uv before building the installer' }
Copy-Item $uvSource (Join-Path $Staging 'bin\uv.exe')

# PoseCap workspace wheels.
Invoke-Checked -Label 'build posecap-contracts wheel' -Command @('uv', 'build', '--wheel', '--package', 'posecap-contracts', '--out-dir', (Join-Path $Staging 'wheels'))
Invoke-Checked -Label 'build posecap-core wheel' -Command @('uv', 'build', '--wheel', '--package', 'posecap-core', '--out-dir', (Join-Path $Staging 'wheels'))
Invoke-Checked -Label 'build posecap-engine wheel' -Command @('uv', 'build', '--wheel', '--package', 'posecap-engine', '--out-dir', (Join-Path $Staging 'wheels'))

# PyTorch3D: repacked from the validated workstation venv (no Windows wheel upstream).
$sitePackages = Join-Path $RepoRoot '.venv-pear\Lib\site-packages'
if (-not (Test-Path (Join-Path $sitePackages 'pytorch3d'))) {
    throw ".venv-pear with a built PyTorch3D not found -- run tools\install\setup_pear_runtime.ps1 first"
}
Invoke-Checked -Label 'repack pytorch3d wheel' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\repack_wheel.py'),
    '--site-packages', $sitePackages,
    '--distribution', 'pytorch3d',
    '--output-dir', (Join-Path $Staging 'wheels')
)

# Blender extension zip.
Invoke-Checked -Label 'build Blender extension' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\build_extension.py'),
    '--output-dir', (Join-Path $Staging 'extension'),
    '--staging-dir', (Join-Path $ScriptRoot 'work\extension-stage'),
    '--release'
)

# Bootstrap, lockfiles, manifest, licenses.
Copy-Item (Join-Path $ScriptRoot 'installer\bootstrap_install.ps1') (Join-Path $Staging 'bootstrap\bootstrap_install.ps1')
Copy-Item (Join-Path $ScriptRoot 'requirements-torch.lock') $Staging
Copy-Item (Join-Path $ScriptRoot 'requirements-pypi.lock') $Staging
Copy-Item (Join-Path $RepoRoot 'LICENSE') $Staging

$manifest = [ordered]@{
    version        = $displayLabel
    pearRevision   = $pearRevision
    pearArchiveUrl = "https://github.com/Pixel-Talk/PEAR/archive/$pearRevision.zip"
    torchIndexUrl  = 'https://download.pytorch.org/whl/cu124'
}
$manifest | ConvertTo-Json | Out-File -Encoding utf8 (Join-Path $Staging 'installer_manifest.json')

@"
# Third-party notices

Downloaded or bundled by the PoseCap installer, each under its own license:

- PEAR (Pixel-Talk/PEAR, pinned $pearRevision) -- research code, see upstream repository license.
- PEAR model weights (Hugging Face BestWJH/PEAR_models, pinned revision) -- Apache-2.0.
- PyTorch3D 0.7.9 (facebookresearch/pytorch3d, repacked build) -- BSD-3-Clause.
- PyTorch / Torchvision cu124 wheels -- BSD-style, see pytorch.org.
- YOLOv8x weights via Ultralytics -- AGPL-3.0 (weights fetched at install time).
- uv (Astral) -- MIT/Apache-2.0.
- CPython 3.11 (python-build-standalone) -- PSF license.
- Python dependencies from PyPI per requirements-pypi.lock -- respective licenses.

SMPL-X body models are licensed by MPI / Meshcapade and are neither bundled nor
downloaded by this installer.
"@ | Out-File -Encoding utf8 (Join-Path $Staging 'THIRD_PARTY_NOTICES.md')

# --- Render + compile -----------------------------------------------------------
$outputBase = "PoseCap_v${displayLabel}_Windows_Setup"
# -Encoding UTF8: PS 5.1 Get-Content defaults to the ANSI codepage, which turns
# any non-ASCII (an em-dash) into mojibake baked into the compiled installer.
$template = Get-Content (Join-Path $ScriptRoot 'installer\posecap.iss.template') -Raw -Encoding UTF8
$rendered = $template `
    -replace '@@APP_VERSION@@', $displayLabel `
    -replace '@@BASE_VERSION@@', $baseVersion `
    -replace '@@DISPLAY_LABEL@@', $displayLabel `
    -replace '@@OUTPUT_BASENAME@@', $outputBase `
    -replace '@@STAGING@@', $Staging
if ($rendered -match '@@[A-Z_]+@@') { throw "unrendered token remains: $($Matches[0])" }
$iss = Join-Path $ScriptRoot 'work\posecap.iss'
$rendered | Out-File -Encoding utf8 $iss

$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
    'C:\Program Files\Inno Setup 6\ISCC.exe'
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source }
if (-not $iscc) { throw 'Inno Setup 6 (ISCC.exe) not found -- winget install JRSoftware.InnoSetup' }

Invoke-Checked -Label "compile installer with $iscc" -Command @($iscc, "/O$Dist", $iss)

$setup = Join-Path $Dist "$outputBase.exe"
$sha = (Get-FileHash -Algorithm SHA256 $setup).Hash
Write-Host ''
Write-Host "==> built: $setup"
Write-Host "    sha256: $sha"
Write-Host "    size:   $([math]::Round((Get-Item $setup).Length / 1MB, 1)) MB"
