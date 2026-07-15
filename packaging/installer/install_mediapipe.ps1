# MediaPipe Lite Pose Backend component handler.
#
# This runtime is deliberately isolated from PEAR: CPU-only MediaPipe packages,
# the official Apache-2.0 task bundle, and PoseCap's three shared wheels live
# under backends\mediapipe and never import a CUDA or licensed-model dependency.

#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-StrictMode -Version Latest

$PayloadDir = Join-Path $InstallDir "payloads\mediapipe"
$Uv = Join-Path $PayloadDir "bin\uv.exe"
$Wheels = Join-Path $PayloadDir "wheels"
$Lock = Join-Path $PayloadDir "requirements-mediapipe.lock"
$BackendDir = Join-Path $InstallDir "backends\mediapipe"
$PythonDir = Join-Path $BackendDir "python"
$VenvDir = Join-Path $BackendDir "runtime"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$Launcher = Join-Path $VenvDir "Scripts\posecap-mediapipe.exe"
$ModelPath = Join-Path $BackendDir "models\holistic_landmarker.task"
$BackendManifestPath = Join-Path $BackendDir "backend.json"
$InventoryPath = Join-Path $InstallDir "installed_components.json"
$env:UV_PYTHON_INSTALL_DIR = $PythonDir

function Invoke-MediaPipeStep {
    param([string]$Label, [scriptblock]$Action, [string]$Fix)
    Write-Host ""
    Write-Host "==> $Label"
    try { & $Action }
    catch { throw "$Label -- $($_.Exception.Message). How to fix: $Fix" }
}

function Invoke-Uv {
    param([string[]]$Arguments)
    & $Uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv exited with code $LASTEXITCODE" }
}

function Test-MediaPipeDoctorAcceptsRuntime {
    if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath $ModelPath -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath $BackendManifestPath -PathType Leaf)) { return $false }
    & $Launcher doctor --model-path $ModelPath | Out-Host
    return $LASTEXITCODE -eq 0
}

$sameVersionRepair = $false
if (Test-Path -LiteralPath $InventoryPath -PathType Leaf) {
    $inventory = Get-Content $InventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $sameVersionRepair = $inventory.transaction_state -eq "installing" -and
        $null -ne $inventory.previous_version -and
        [string]$inventory.previous_version -eq [string]$inventory.version
}
if ($sameVersionRepair -and (Test-MediaPipeDoctorAcceptsRuntime)) {
    Write-Host "MediaPipe Lite runtime is healthy and already matches this installer; preserving it."
    return
}

Invoke-MediaPipeStep -Label "Verify the MediaPipe component payload" `
    -Fix "Reinstall PoseCap; the selected MediaPipe component payload is incomplete." `
    -Action {
        foreach ($required in @($Uv, $Lock, $ModelPath)) {
            if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
                throw "required component file is missing: $required"
            }
        }
        $bundled = @(Get-ChildItem -LiteralPath $Wheels -Filter *.whl -ErrorAction Stop)
        if ($bundled.Count -ne 3) { throw "expected three PoseCap wheels in $Wheels" }
    }

Invoke-MediaPipeStep -Label "Install Python 3.11 runtime (app-local, via uv)" `
    -Fix "Check your internet connection and run PoseCap Setup (repair)." `
    -Action { Invoke-Uv @("python", "install", "--no-bin", "--no-registry", "3.11") }

Invoke-MediaPipeStep -Label "Create the isolated MediaPipe environment" `
    -Fix "Close Blender, then run PoseCap Setup (repair)." `
    -Action { Invoke-Uv @("venv", "--clear", "--python", "3.11", $VenvDir) }

Invoke-MediaPipeStep -Label "Install MediaPipe CPU dependencies" `
    -Fix "Check your internet connection and disk space, then run PoseCap Setup (repair)." `
    -Action { Invoke-Uv @("pip", "install", "--python", $VenvPython, "-r", $Lock) }

Invoke-MediaPipeStep -Label "Install PoseCap bridge" `
    -Fix "Reinstall PoseCap; the bundled MediaPipe component is incomplete." `
    -Action {
        $bundled = @(Get-ChildItem -LiteralPath $Wheels -Filter *.whl | ForEach-Object { $_.FullName })
        Invoke-Uv (@("pip", "install", "--python", $VenvPython, "--no-deps") + $bundled)
    }

Invoke-MediaPipeStep -Label "Verify MediaPipe Lite runtime" `
    -Fix "Run PoseCap Setup (repair); the model or CPU runtime could not be loaded." `
    -Action {
        & $Launcher doctor --model-path $ModelPath | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "MediaPipe doctor reported a failing check" }
    }

Invoke-MediaPipeStep -Label "Register MediaPipe Lite pose backend" `
    -Fix "Run PoseCap Setup (repair); the runtime exists but its registration failed." `
    -Action {
        New-Item -ItemType Directory -Force -Path $BackendDir | Out-Null
        $backendManifest = [ordered]@{
            schema_version = 1
            id = "mediapipe"
            display_name = "MediaPipe Lite (CPU)"
            command = @($Launcher, "live", "--model-path", $ModelPath)
            protocol_versions = @(1)
            capabilities = @("body")
            requires_body_models = $false
            apply_orientation_fix = $false
            compatibility = [ordered]@{
                operating_systems = @("windows", "linux", "macos")
                accelerators = @("cpu")
                account = "No account required"
                license = "Apache-2.0 (MediaPipe package and model bundle)"
            }
        }
        $temp = "$BackendManifestPath.tmp"
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($temp, ($backendManifest | ConvertTo-Json -Depth 4), $utf8NoBom)
        Move-Item -Force -LiteralPath $temp -Destination $BackendManifestPath
    }
