# PoseCap modular post-install coordinator (task 0022).

#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallDir = "",
    [string]$Components = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrEmpty($InstallDir)) {
    $InstallDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$BootstrapDir = Join-Path $InstallDir "bootstrap"
$ManifestPath = Join-Path $InstallDir "installer_manifest.json"
$LogDir = Join-Path $InstallDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogPath = Join-Path $LogDir ("bootstrap-{0}.log" -f (Get-Date -Format "yyyyMMddTHHmmss"))
Start-Transcript -Path $LogPath -Force | Out-Null

function Stop-WithFailure {
    param([string]$What)
    Write-Host ""
    Write-Host "SETUP FAILED: $What" -ForegroundColor Red
    Write-Host "Run PoseCap Setup (repair), then share the newest log if it still fails."
    Write-Host "Full log: $LogPath"
    Stop-Transcript | Out-Null
    exit 1
}

try {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "installer_manifest.json not found at $ManifestPath"
    }
    $manifest = Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($Components)) {
        $inventoryPath = Join-Path $InstallDir "installed_components.json"
        if (Test-Path -LiteralPath $inventoryPath -PathType Leaf) {
            $inventory = Get-Content $inventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $Components = @($inventory.components.PSObject.Properties.Name) -join ','
        }
        else {
            $Components = "base"
        }
    }
    $SelectedComponents = @($Components.Split(','))

    Write-Host "PoseCap component setup"
    Write-Host "Install dir: $InstallDir"
    Write-Host "Components:  $Components"
    Write-Host "Log:         $LogPath"

    & (Join-Path $BootstrapDir "component_lifecycle.ps1") `
        -InstallDir $InstallDir -Action Begin -Components $Components -Version $manifest.version

    & (Join-Path $BootstrapDir "install_base.ps1") -InstallDir $InstallDir

    & (Join-Path $BootstrapDir "component_lifecycle.ps1") `
        -InstallDir $InstallDir -Action BaseReady -Components $Components -Version $manifest.version

    if ($SelectedComponents -contains "mediapipe") {
        & (Join-Path $BootstrapDir "install_mediapipe.ps1") -InstallDir $InstallDir
    }

    if ($SelectedComponents -contains "pear") {
        & (Join-Path $BootstrapDir "install_pear.ps1") -InstallDir $InstallDir
    }

    & (Join-Path $BootstrapDir "component_lifecycle.ps1") `
        -InstallDir $InstallDir -Action Complete -Components $Components -Version $manifest.version

    Set-Content -Path (Join-Path $LogDir "SETUP_OK") -Value (Get-Date -Format "o") -Encoding ascii
}
catch {
    Stop-WithFailure -What $_.Exception.Message
}

Write-Host ""
Write-Host "PoseCap setup complete." -ForegroundColor Green
Write-Host "Open Blender, press N in the 3D Viewport, and choose the PoseCap tab."
Write-Host "PoseCap lists installed pose backends in its panel; choose one when several are ready."
Stop-Transcript | Out-Null
exit 0
