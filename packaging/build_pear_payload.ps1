# Build the external PEAR bootstrap payload consumed by the online installer.
#
#   powershell -ExecutionPolicy Bypass -File packaging\build_pear_payload.ps1 `
#     -Pytorch3dSitePackages C:\path\to\.venv-pear\Lib\site-packages `
#     -BaseUrl https://github.com/CorridorTech/PoseCap/releases/download/<tag>

#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(1, 999999)] [int]$BuildNumber = 1,
    [Parameter(Mandatory = $true)] [string]$Pytorch3dSitePackages,
    [Parameter(Mandatory = $true)] [string]$BaseUrl,
    [string]$OutputDir = ""
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $ScriptRoot 'dist'
}
$Staging = Join-Path $ScriptRoot 'work\pear-payload-staging'
$resolvedWorkRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptRoot 'work'))
$resolvedStaging = [System.IO.Path]::GetFullPath($Staging)
if (-not $resolvedStaging.StartsWith(
    $resolvedWorkRoot + [System.IO.Path]::DirectorySeparatorChar,
    [System.StringComparison]::OrdinalIgnoreCase
)) {
    throw "refusing to clean staging outside packaging work: $resolvedStaging"
}
if (Test-Path -LiteralPath $resolvedStaging) {
    Remove-Item -Recurse -Force -LiteralPath $resolvedStaging
}
New-Item -ItemType Directory -Force -Path `
    (Join-Path $resolvedStaging 'bin'),
    (Join-Path $resolvedStaging 'wheels'),
    $OutputDir | Out-Null

function Invoke-Checked {
    param([string]$Label, [string[]]$Command)
    Write-Host "==> $Label"
    $program = $Command[0]
    $arguments = @()
    if ($Command.Count -gt 1) { $arguments = $Command[1..($Command.Count - 1)] }
    & $program @arguments | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

$pyproject = Get-Content (Join-Path $RepoRoot 'pyproject.toml') -Raw -Encoding UTF8
if ($pyproject -notmatch 'version = "([^"]+)"') { throw 'version not found in pyproject.toml' }
$baseVersion = $Matches[1]
$displayLabel = "$baseVersion-win.$BuildNumber"

$configPy = Get-Content `
    (Join-Path $RepoRoot 'engine\src\posecap_engine\config.py') -Raw -Encoding UTF8
if ($configPy -notmatch 'PEAR_REVISION = "([0-9a-f]{40})"') {
    throw 'PEAR_REVISION not found in engine config'
}
$pearRevision = $Matches[1]

$uvSource = (Get-Command uv -ErrorAction SilentlyContinue).Source
if ($null -eq $uvSource) { throw 'uv not found on PATH' }
Copy-Item -LiteralPath $uvSource -Destination (Join-Path $resolvedStaging 'bin\uv.exe')

foreach ($package in @('posecap-contracts', 'posecap-core', 'posecap-engine')) {
    Invoke-Checked -Label "build $package wheel" -Command @(
        'uv', 'build', '--wheel', '--package', $package,
        '--out-dir', (Join-Path $resolvedStaging 'wheels')
    )
}

$resolvedSitePackages = (Resolve-Path -LiteralPath $Pytorch3dSitePackages).Path
if (-not (Test-Path -LiteralPath (Join-Path $resolvedSitePackages 'pytorch3d'))) {
    throw "pytorch3d package not found in $resolvedSitePackages"
}
Invoke-Checked -Label 'repack pytorch3d wheel' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\repack_wheel.py'),
    '--site-packages', $resolvedSitePackages,
    '--distribution', 'pytorch3d',
    '--output-dir', (Join-Path $resolvedStaging 'wheels')
)
Remove-Item `
    -Force -LiteralPath (Join-Path $resolvedStaging 'wheels\.gitignore') `
    -ErrorAction SilentlyContinue

Copy-Item `
    (Join-Path $ScriptRoot 'requirements-torch.lock') `
    (Join-Path $resolvedStaging 'requirements-torch.lock')
Copy-Item `
    (Join-Path $ScriptRoot 'requirements-pypi.lock') `
    (Join-Path $resolvedStaging 'requirements-pypi.lock')

$pearSourceLockPath = Join-Path $ScriptRoot 'pear-source.lock.json'
$pearSourceLock = Get-Content $pearSourceLockPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$pearSourceLock.revision -ne $pearRevision) {
    throw "PEAR source lock revision does not match engine config: $($pearSourceLock.revision)"
}

Invoke-Checked -Label 'package external PEAR bootstrap' -Command @(
    'uv', 'run', 'python', (Join-Path $RepoRoot 'tools\build_pear_payload.py'),
    '--source', $resolvedStaging,
    '--version', $displayLabel,
    '--base-url', $BaseUrl,
    '--pear-source-url', [string]$pearSourceLock.url,
    '--pear-source-sha256', [string]$pearSourceLock.sha256,
    '--pear-source-size', [string]$pearSourceLock.size_bytes,
    '--output-dir', $OutputDir
)

$archive = Join-Path $OutputDir "posecap-pear-bootstrap-$displayLabel.zip"
$manifest = Join-Path $OutputDir "posecap-pear-bootstrap-$displayLabel.json"
Write-Host "==> payload:  $archive"
Write-Host "    manifest: $manifest"
