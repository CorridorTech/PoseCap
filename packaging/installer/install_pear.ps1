# PEAR pose-backend component handler (task 0022).

#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDir
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
Set-StrictMode -Version Latest

$Uv = Join-Path $InstallDir "bin\uv.exe"
$Wheels = Join-Path $InstallDir "wheels"
$PythonDir = Join-Path $InstallDir "python"
$VenvDir = Join-Path $InstallDir "runtime\venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PearDir = Join-Path $InstallDir "pear"
$ManifestPath = Join-Path $InstallDir "installer_manifest.json"
$InventoryPath = Join-Path $InstallDir "installed_components.json"
$PearBackendDir = Join-Path $InstallDir "backends\pear"
$PearBackendManifestPath = Join-Path $PearBackendDir "backend.json"
$PearSourceArchive = Join-Path $InstallDir "payloads\pear\pear-source.zip"
$env:UV_PYTHON_INSTALL_DIR = $PythonDir

function Invoke-PearStep {
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

function Test-PearDoctorAcceptsRuntime {
    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) { return $false }
    if (-not (Test-Path -LiteralPath (Join-Path $PearDir "configs\infer.yaml") -PathType Leaf)) {
        return $false
    }
    if (-not (Test-Path -LiteralPath $PearBackendManifestPath -PathType Leaf)) { return $false }

    $doctorOut = & $VenvPython -m posecap_engine.cli doctor --pear-root $PearDir
    $doctorExit = $LASTEXITCODE
    $doctorOut | Out-Host
    if ($doctorExit -eq 0) { return $true }
    $report = $null
    try {
        $report = $doctorOut | Where-Object { $_ -like '{*' } |
            Select-Object -Last 1 | ConvertFrom-Json
    }
    catch { return $false }
    if ($null -eq $report) { return $false }
    $errors = @($report.checks | Where-Object { $_.status -eq 'error' } |
        ForEach-Object { $_.name })
    return $errors.Count -ge 1 -and
        (@($errors | Where-Object { $_ -ne 'pear_assets' }).Count -eq 0)
}

$Manifest = $null
Invoke-PearStep -Label "Read installer manifest" `
    -Fix "Reinstall PoseCap; the installed tree is incomplete." `
    -Action {
        if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
            throw "installer_manifest.json not found at $ManifestPath"
        }
        $script:Manifest = Get-Content $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }

$sameVersionRepair = $false
if (Test-Path -LiteralPath $InventoryPath -PathType Leaf) {
    $inventory = Get-Content $InventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $sameVersionRepair = $inventory.transaction_state -eq "installing" -and
        $null -ne $inventory.previous_version -and
        [string]$inventory.previous_version -eq [string]$inventory.version
}
if ($sameVersionRepair -and (Test-PearDoctorAcceptsRuntime)) {
    Write-Host "PEAR runtime is healthy and already matches this installer; preserving it."
    return
}

Invoke-PearStep -Label "Check NVIDIA driver (nvidia-smi)" `
    -Fix "Install the NVIDIA driver for your RTX GPU from nvidia.com/drivers, then run PoseCap Setup (repair)." `
    -Action {
        $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($null -eq $smi) { throw "nvidia-smi not found -- no NVIDIA driver detected" }
        $smiOutput = & $smi.Source 2>&1
        if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed -- driver present but not healthy" }
        $smiOutput | Select-Object -First 12 | Out-Host
    }

Invoke-PearStep -Label "Install Python 3.11 runtime (app-local, via uv)" `
    -Fix "Check your internet connection and re-run setup. Corporate proxies: set HTTPS_PROXY first." `
    -Action { Invoke-Uv @("python", "install", "--no-bin", "--no-registry", "3.11") }

Invoke-PearStep -Label "Create engine virtual environment" `
    -Fix "Delete '$VenvDir' and re-run setup." `
    -Action { Invoke-Uv @("venv", "--clear", "--python", "3.11", $VenvDir) }

Invoke-PearStep -Label "Install PyTorch CUDA 12.4 wheels (~2.5 GB download)" `
    -Fix "Check your internet connection and disk space (needs ~8 GB free), then re-run setup." `
    -Action {
        Invoke-Uv @(
            "pip", "install", "--python", $VenvPython,
            "--index-url", $Manifest.torchIndexUrl,
            "-r", (Join-Path $InstallDir "requirements-torch.lock")
        )
    }

Invoke-PearStep -Label "Install engine dependencies" `
    -Fix "Check your internet connection, then re-run setup." `
    -Action {
        Invoke-Uv @(
            "pip", "install", "--python", $VenvPython,
            "-r", (Join-Path $InstallDir "requirements-pypi.lock")
        )
    }

Invoke-PearStep -Label "Install bundled wheels (PoseCap engine + PyTorch3D)" `
    -Fix "Reinstall PoseCap; the bundled wheels are missing or corrupt." `
    -Action {
        $bundled = @(Get-ChildItem -Path $Wheels -Filter *.whl | ForEach-Object { $_.FullName })
        if ($bundled.Count -lt 4) {
            throw "expected at least 4 bundled wheels in $Wheels, found $($bundled.Count)"
        }
        Invoke-Uv (@("pip", "install", "--python", $VenvPython) + $bundled)
    }

Invoke-PearStep -Label "Fetch PEAR model code (pinned revision $($Manifest.pearRevision))" `
    -Fix "Re-run the installer; the verified PEAR component payload is incomplete." `
    -Action {
        $marker = Join-Path $PearDir "configs\infer.yaml"
        $revisionMarker = Join-Path $PearDir ".posecap-source-revision"
        $installedRevision = ""
        if (Test-Path -LiteralPath $revisionMarker -PathType Leaf) {
            $installedRevision = [System.IO.File]::ReadAllText($revisionMarker).Trim()
        }
        if ((Test-Path -LiteralPath $marker -PathType Leaf) -and
            $installedRevision -eq [string]$Manifest.pearRevision) {
            Write-Host "    already present -- preserving code and user-acquired data"
            return
        }
        $extractDir = Join-Path $env:TEMP "posecap-pear-extract-$([guid]::NewGuid())"
        if (-not (Test-Path -LiteralPath $PearSourceArchive -PathType Leaf)) {
            throw "verified PEAR source archive not found at $PearSourceArchive"
        }
        try {
            Expand-Archive -LiteralPath $PearSourceArchive -DestinationPath $extractDir -Force
            $inner = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
            if ($null -eq $inner) { throw "PEAR archive extracted empty" }
            foreach ($required in @("models", "utils", "configs\infer.yaml")) {
                if (-not (Test-Path -LiteralPath (Join-Path $inner.FullName $required))) {
                    throw "PEAR archive is missing expected path '$required'"
                }
            }
            if (Test-Path -LiteralPath $PearDir) {
                Get-ChildItem -LiteralPath $inner.FullName -Force |
                    Copy-Item -Destination $PearDir -Recurse -Force
            }
            else {
                Move-Item -LiteralPath $inner.FullName -Destination $PearDir
            }
        }
        finally {
            Remove-Item -Recurse -Force -LiteralPath $extractDir -ErrorAction SilentlyContinue
        }
        foreach ($required in @("models", "utils", "configs\infer.yaml")) {
            if (-not (Test-Path -LiteralPath (Join-Path $PearDir $required))) {
                throw "PEAR checkout is missing expected path '$required'"
            }
        }
        Set-Content -LiteralPath (Join-Path $PearDir ".posecap-source-revision") -Value $Manifest.pearRevision -NoNewline
    }

Invoke-PearStep -Label "Fetch YOLO person-detection weights" `
    -Fix "Check your internet connection, then re-run setup." `
    -Action {
        $modelZoo = Join-Path $PearDir "model_zoo"
        $yolo = Join-Path $modelZoo "yolov8s.pt"
        if (Test-Path -LiteralPath $yolo -PathType Leaf) {
            Write-Host "    already present -- skipping download"
            return
        }
        New-Item -ItemType Directory -Force -Path $modelZoo | Out-Null
        Push-Location $modelZoo
        try {
            & $VenvPython -c "from ultralytics import YOLO; YOLO('yolov8s.pt')" | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "ultralytics download exited with code $LASTEXITCODE" }
        }
        finally { Pop-Location }
        if (-not (Test-Path -LiteralPath $yolo -PathType Leaf)) {
            throw "yolov8s.pt did not appear in $modelZoo"
        }
    }

$LicensedModelsPending = $false
Invoke-PearStep -Label "Verify install (doctor) and fetch pose-model weights (~2.6 GB)" `
    -Fix "Read the doctor output; every failing check names its own fix." `
    -Action {
        $doctorOut = & $VenvPython -m posecap_engine.cli doctor --pear-root $PearDir --download-weights
        $doctorExit = $LASTEXITCODE
        $doctorOut | Out-Host
        if ($doctorExit -eq 0) { return }
        $report = $null
        try {
            $report = $doctorOut | Where-Object { $_ -like '{*' } |
                Select-Object -Last 1 | ConvertFrom-Json
        }
        catch {}
        if ($null -eq $report) { throw "doctor reported failing checks" }
        $errors = @($report.checks | Where-Object { $_.status -eq 'error' } |
            ForEach-Object { $_.name })
        if ($errors.Count -ge 1 -and
            (@($errors | Where-Object { $_ -ne 'pear_assets' }).Count -eq 0)) {
            $script:LicensedModelsPending = $true
            return
        }
        throw "doctor reported failing checks: $($errors -join ', ')"
    }

$EnginePath = Join-Path $VenvDir "Scripts\posecap-engine.exe"
Invoke-PearStep -Label "Register PEAR pose backend" `
    -Fix "Run PoseCap Setup (repair); the runtime exists but its registration failed." `
    -Action {
        New-Item -ItemType Directory -Force -Path $PearBackendDir | Out-Null
        $backendManifest = [ordered]@{
            schema_version = 1
            id = "pear"
            display_name = "PEAR (NVIDIA CUDA)"
            command = @($EnginePath, "live", "--pear-root", $PearDir)
            protocol_versions = @(1)
            capabilities = @("body", "hands", "face")
            compatibility = [ordered]@{
                operating_systems = @("windows")
                accelerators = @("nvidia-cuda")
                account = "MPI account required for model downloads"
                license = "MPI model terms apply; commercial use requires a Meshcapade license"
            }
        }
        $backendJson = $backendManifest | ConvertTo-Json -Depth 4
        $backendManifestTemp = "$PearBackendManifestPath.tmp"
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($backendManifestTemp, $backendJson, $utf8NoBom)
        Move-Item -Force -LiteralPath $backendManifestTemp -Destination $PearBackendManifestPath
    }

if ($LicensedModelsPending) {
    Write-Host ""
    Write-Host "ACTION REQUIRED - licensed body models (one-time):" -ForegroundColor Yellow
    Write-Host "SMPL/SMPL-X/FLAME body models cannot ship with PoseCap."
    Write-Host "Use Blender's PoseCap > Body Models setup, then run PoseCap Doctor."
    Write-Host "  https://github.com/CorridorTech/PoseCap/blob/main/doc/guides/smplx-model-setup.md"
}
