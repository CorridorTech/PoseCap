# Switch the installed PEAR runtime between the default CUDA 12.8 matrix and
# the opt-in CUDA 12.4 matrix that restores pre-Blackwell throughput (ADR-0019).
# The choice persists in pear_runtime.json, so upgrades and repairs keep it.

#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [ValidateSet("cu128", "cu124")] [string]$Runtime,
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "native_command.ps1")
. (Join-Path $PSScriptRoot "pear_runtime.ps1")

if ([string]::IsNullOrEmpty($InstallDir)) {
    $InstallDir = Split-Path -Parent $PSScriptRoot
}

$LogDir = Join-Path $InstallDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("switch-pear-runtime-{0}.log" -f (Get-Date -Format "yyyyMMddTHHmmss"))
Start-Transcript -Path $LogPath -Force | Out-Null

function Stop-WithFailure {
    param([string]$What)
    Write-Host ""
    Write-Host "RUNTIME SWITCH FAILED: $What" -ForegroundColor Red
    Write-Host "Full log: $LogPath"
    Stop-Transcript | Out-Null
    exit 1
}

$previous = $null
try {
    if (-not (Test-Path -LiteralPath (Join-Path $InstallDir "backends\pear\backend.json") -PathType Leaf)) {
        throw "PEAR is not installed. Run PoseCap Setup and select the PEAR component first."
    }
    $manifest = Get-Content (Join-Path $InstallDir "installer_manifest.json") -Raw -Encoding UTF8 |
        ConvertFrom-Json
    if ($Runtime -eq $PearLegacyRuntime) {
        $blocking = @(Get-PearLegacyBlockingGpus -SmiOutput (Read-NvidiaGpuCapabilities))
        if ($blocking.Count -gt 0) {
            throw ("the CUDA 12.4 runtime cannot drive $($blocking -join '; '). " +
                "RTX 50-series GPUs need the default CUDA 12.8 runtime.")
        }
    }
    # Fails before anything changes when the installed payload lacks the runtime.
    $null = Get-PearRuntimeSpec -InstallDir $InstallDir -Runtime $Runtime `
        -DefaultIndexUrl $manifest.torchIndexUrl

    $previous = Get-PearRuntimeSelection -InstallDir $InstallDir
    Write-Host "PoseCap PEAR runtime switch: $previous -> $Runtime"
    Write-Host "Close Blender before continuing; a running capture holds the runtime open."
    Write-Host "Log: $LogPath"

    Set-PearRuntimeSelection -InstallDir $InstallDir -Runtime $Runtime
    & (Join-Path $PSScriptRoot "install_pear.ps1") -InstallDir $InstallDir
}
catch {
    if ($null -ne $previous) {
        # Point repair back at the runtime that last worked.
        Set-PearRuntimeSelection -InstallDir $InstallDir -Runtime $previous
        Write-Host "Restored the $previous preference; PoseCap Setup (repair) reinstalls it."
    }
    Stop-WithFailure -What $_.Exception.Message
}

Write-Host ""
Write-Host "PEAR now uses the $Runtime runtime." -ForegroundColor Green
Write-Host "Restart Blender if it was open."
Stop-Transcript | Out-Null
exit 0
