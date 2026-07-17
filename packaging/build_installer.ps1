# Build the PoseCap Windows installer (task 0006; CK2P pattern, light flavor).
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1 `
#     -PearPayloadManifest packaging\dist\posecap-pear-bootstrap-<version>.json `
#     -MediaPipePayloadManifest packaging\dist\posecap-mediapipe-bootstrap-<version>.json
#
# Stages PoseCap Base, renders the checksummed external PEAR payload entry, and
# compiles the setup exe into packaging\dist.
#
# Requires on the BUILD machine: uv, Inno Setup 6 (ISCC), and a payload manifest
# produced by build_pear_payload.ps1. End-user machines need none of this.

#Requires -Version 5.1
[CmdletBinding()]
param(
    # 0 is reserved for dev builds; a shipped installer carries a real id.
    [ValidateRange(1, 999999)] [int]$BuildNumber = 1,
    [Parameter(Mandatory = $true)] [string]$PearPayloadManifest,
    [Parameter(Mandatory = $true)] [string]$MediaPipePayloadManifest
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
    (Join-Path $Staging 'extension'), (Join-Path $Staging 'bootstrap') | Out-Null

# Blender extension zip.
Invoke-Checked -Label 'build Blender extension' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\build_extension.py'),
    '--output-dir', (Join-Path $Staging 'extension'),
    '--staging-dir', (Join-Path $ScriptRoot 'work\extension-stage'),
    '--release'
)

# Bootstrap, manifests, and licenses.
foreach ($bootstrapScript in @(
    'bootstrap_install.ps1',
    'blender_discovery.ps1',
    'component_lifecycle.ps1',
    'native_command.ps1',
    'probe_blender.ps1',
    'install_base.ps1',
    'install_mediapipe.ps1',
    'install_pear.ps1',
    'uninstall_base.ps1'
)) {
    Copy-Item `
        (Join-Path $ScriptRoot "installer\$bootstrapScript") `
        (Join-Path $Staging "bootstrap\$bootstrapScript")
}
Copy-Item (Join-Path $RepoRoot 'LICENSE') $Staging
if (-not (Test-Path -LiteralPath $PearPayloadManifest -PathType Leaf)) {
    throw "PEAR payload manifest not found: $PearPayloadManifest"
}
$pearPayloadManifestPath = (Resolve-Path -LiteralPath $PearPayloadManifest).Path
Copy-Item $pearPayloadManifestPath (Join-Path $Staging 'pear_payload_manifest.json')
$pearPayload = Get-Content -LiteralPath $pearPayloadManifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json
if (-not (Test-Path -LiteralPath $MediaPipePayloadManifest -PathType Leaf)) {
    throw "MediaPipe payload manifest not found: $MediaPipePayloadManifest"
}
$mediaPipePayloadManifestPath = (Resolve-Path -LiteralPath $MediaPipePayloadManifest).Path
Copy-Item $mediaPipePayloadManifestPath (Join-Path $Staging 'mediapipe_payload_manifest.json')
$mediaPipePayload = Get-Content -LiteralPath $mediaPipePayloadManifestPath -Raw -Encoding UTF8 |
    ConvertFrom-Json

$manifest = [ordered]@{
    version       = $displayLabel
    pearRevision  = $pearRevision
    pearPayload   = $pearPayload.archive
    pearSource    = $pearPayload.pear_source
    mediaPipePayload = $mediaPipePayload.archive
    mediaPipeModel = $mediaPipePayload.model
    torchIndexUrl = 'https://download.pytorch.org/whl/cu128'
}
$manifest | ConvertTo-Json | Out-File -Encoding utf8 (Join-Path $Staging 'installer_manifest.json')

@"
# Third-party notices

Downloaded or bundled by the PoseCap installer, each under its own license:

- PEAR (Pixel-Talk/PEAR, pinned $pearRevision) -- fetched directly from upstream; see upstream terms.
- PEAR model weights (Hugging Face BestWJH/PEAR_models, pinned revision) -- Apache-2.0.
- MediaPipe 0.10.35 and Holistic Landmarker task bundle -- Apache-2.0.
- PyTorch3D 0.7.9 (facebookresearch/pytorch3d, repacked build) -- BSD-3-Clause.
- PyTorch / Torchvision cu128 wheels -- BSD-style, see pytorch.org.
- YOLOv8x weights via Ultralytics -- AGPL-3.0 (weights fetched at install time).
- uv (Astral) -- MIT/Apache-2.0.
- CPython 3.11 (python-build-standalone) -- PSF license.
- Python dependencies from PyPI per requirements-pypi.lock -- respective licenses.

PoseCap does not bundle or redistribute PEAR's upstream archive or user-acquired
SMPL-X body-model files. MPI / Meshcapade terms remain applicable.
"@ | Out-File -Encoding utf8 (Join-Path $Staging 'THIRD_PARTY_NOTICES.md')

# --- Render + compile -----------------------------------------------------------
$outputBase = "PoseCap_v${displayLabel}_Windows_Setup"
$iss = Join-Path $ScriptRoot 'work\posecap.iss'
Invoke-Checked -Label 'render online installer' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\render_windows_installer.py'),
    '--template', (Join-Path $ScriptRoot 'installer\posecap.iss.template'),
    '--payload-manifest', $pearPayloadManifestPath,
    '--mediapipe-payload-manifest', $mediaPipePayloadManifestPath,
    '--staging', $Staging,
    '--app-version', $displayLabel,
    '--base-version', $baseVersion,
    '--output-basename', $outputBase,
    '--output', $iss
)

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
