# Build the external MediaPipe Lite bootstrap used by the suite installer.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_mediapipe_payload.ps1 `
#     -BaseUrl https://github.com/CorridorTech/PoseCap/releases/download/<tag>

#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(1, 999999)] [int]$BuildNumber = 1,
    [Parameter(Mandatory = $true)] [string]$BaseUrl,
    [string]$OutputDir = ""
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ScriptRoot 'dist'
}
$Staging = Join-Path $ScriptRoot 'work\mediapipe-payload-staging'
$WorkRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptRoot 'work'))
$ResolvedStaging = [System.IO.Path]::GetFullPath($Staging)
if (-not $ResolvedStaging.StartsWith(
    $WorkRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "refusing to clean staging outside packaging work: $ResolvedStaging"
}
if (Test-Path -LiteralPath $ResolvedStaging) {
    Remove-Item -Recurse -Force -LiteralPath $ResolvedStaging
}
New-Item -ItemType Directory -Force -Path `
    (Join-Path $ResolvedStaging 'bin'), (Join-Path $ResolvedStaging 'wheels'), $OutputDir | Out-Null

function Invoke-Checked {
    param([string]$Label, [string[]]$Command)
    Write-Host "==> $Label"
    & $Command[0] @($Command | Select-Object -Skip 1) | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

$Pyproject = Get-Content (Join-Path $RepoRoot 'pyproject.toml') -Raw -Encoding UTF8
if ($Pyproject -notmatch 'version = "([^"]+)"') { throw 'version not found in pyproject.toml' }
$DisplayLabel = "$($Matches[1])-win.$BuildNumber"

$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($null -eq $Uv) { throw 'uv not found on PATH' }
Copy-Item -LiteralPath $Uv -Destination (Join-Path $ResolvedStaging 'bin\uv.exe')

foreach ($package in @('posecap-contracts', 'posecap-core', 'posecap-engine')) {
    Invoke-Checked -Label "build $package wheel" -Command @(
        'uv', 'build', '--wheel', '--package', $package,
        '--out-dir', (Join-Path $ResolvedStaging 'wheels')
    )
}
Remove-Item `
    -Force -LiteralPath (Join-Path $ResolvedStaging 'wheels\.gitignore') `
    -ErrorAction SilentlyContinue
Copy-Item `
    (Join-Path $ScriptRoot 'requirements-mediapipe.lock') `
    (Join-Path $ResolvedStaging 'requirements-mediapipe.lock')

Invoke-Checked -Label 'package MediaPipe bootstrap' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\build_mediapipe_payload.py'),
    '--source', $ResolvedStaging,
    '--version', $DisplayLabel,
    '--base-url', $BaseUrl,
    '--model-url', 'https://storage.googleapis.com/mediapipe-models/holistic_landmarker/holistic_landmarker/float16/1/holistic_landmarker.task',
    '--model-sha256', 'e2dab61191e2dcd0a15f943d8e3ed1dce13c82dfa597b9dd39f562975a50c3f8',
    '--model-size', '13683609',
    '--output-dir', $OutputDir
)

Write-Host "==> payload:  $(Join-Path $OutputDir "posecap-mediapipe-bootstrap-$DisplayLabel.zip")"
Write-Host "    manifest: $(Join-Path $OutputDir "posecap-mediapipe-bootstrap-$DisplayLabel.json")"
