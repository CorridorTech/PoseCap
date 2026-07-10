# PoseCap post-install bootstrap (task 0006). Runs on the END USER machine as the
# final installer step, from the installed tree. Everything it needs beyond the
# bundled files comes from canonical pinned sources: python-build-standalone via
# uv, PyPI + download.pytorch.org wheels, the PEAR GitHub archive at the pinned
# revision, and PEAR weights from Hugging Face at the pinned revision.
#
# Contract (task 0006 acceptance criteria): every failure mode prints an
# actionable message, never a raw traceback; the doctor gate at the end is the
# install-and-it-works check.
#
#   powershell -ExecutionPolicy Bypass -File bootstrap_install.ps1 [-InstallDir <dir>]

#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
# PS 5.1: progress-bar rendering throttles Invoke-WebRequest downloads badly.
$ProgressPreference = "SilentlyContinue"
Set-StrictMode -Version Latest

if ([string]::IsNullOrEmpty($InstallDir)) {
    # bootstrap lives at <InstallDir>\bootstrap\bootstrap_install.ps1
    $InstallDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
}

$Uv = Join-Path $InstallDir "bin\uv.exe"
$Wheels = Join-Path $InstallDir "wheels"
$PythonDir = Join-Path $InstallDir "python"
$VenvDir = Join-Path $InstallDir "runtime\venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PearDir = Join-Path $InstallDir "pear"
$LogDir = Join-Path $InstallDir "logs"
$ManifestPath = Join-Path $InstallDir "installer_manifest.json"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$LogPath = Join-Path $LogDir "bootstrap-$Stamp.log"
Start-Transcript -Path $LogPath -Force | Out-Null

$env:UV_PYTHON_INSTALL_DIR = $PythonDir

function Fail {
    param([string]$What, [string]$Fix)
    Write-Host ""
    Write-Host "SETUP FAILED: $What" -ForegroundColor Red
    Write-Host "How to fix:   $Fix"
    Write-Host "Full log:     $LogPath"
    Stop-Transcript | Out-Null
    exit 1
}

function Step {
    param([string]$Label, [scriptblock]$Action, [string]$Fix)
    Write-Host ""
    Write-Host "==> $Label"
    try {
        & $Action
    }
    catch {
        Fail -What "$Label -- $($_.Exception.Message)" -Fix $Fix
    }
}

function Invoke-Uv {
    param([string[]]$Arguments)
    & $Uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv exited with code $LASTEXITCODE" }
}

Write-Host "PoseCap runtime setup"
Write-Host "Install dir: $InstallDir"
Write-Host "Log:         $LogPath"

$Manifest = $null
Step -Label "Read installer manifest" -Fix "Reinstall PoseCap; the installed tree is incomplete." -Action {
    if (-not (Test-Path $ManifestPath)) { throw "installer_manifest.json not found at $ManifestPath" }
    $script:Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
}

Step -Label "Check NVIDIA driver (nvidia-smi)" `
    -Fix "Install the NVIDIA driver for your RTX GPU from nvidia.com/drivers, then re-run this setup from the Start Menu shortcut 'PoseCap Setup (repair)'." `
    -Action {
        $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
        if ($null -eq $smi) { throw "nvidia-smi not found -- no NVIDIA driver detected" }
        $smiOutput = & $smi.Source 2>&1
        if ($LASTEXITCODE -ne 0) { throw "nvidia-smi failed -- driver present but not healthy" }
        $smiOutput | Select-Object -First 12 | Out-Host
    }

Step -Label "Install Python 3.11 runtime (app-local, via uv)" `
    -Fix "Check your internet connection and re-run setup. Corporate proxies: set HTTPS_PROXY first." `
    -Action { Invoke-Uv @("python", "install", "3.11") }

Step -Label "Create engine virtual environment" `
    -Fix "Delete '$VenvDir' and re-run setup." `
    -Action { Invoke-Uv @("venv", "--python", "3.11", $VenvDir) }

Step -Label "Install PyTorch CUDA 12.4 wheels (~2.5 GB download)" `
    -Fix "Check your internet connection and disk space (needs ~8 GB free), then re-run setup." `
    -Action {
        Invoke-Uv @(
            "pip", "install", "--python", $VenvPython,
            "--index-url", $Manifest.torchIndexUrl,
            "-r", (Join-Path $InstallDir "requirements-torch.lock")
        )
    }

Step -Label "Install engine dependencies" `
    -Fix "Check your internet connection, then re-run setup." `
    -Action {
        Invoke-Uv @(
            "pip", "install", "--python", $VenvPython,
            "-r", (Join-Path $InstallDir "requirements-pypi.lock")
        )
    }

Step -Label "Install bundled wheels (PoseCap engine + PyTorch3D)" `
    -Fix "Reinstall PoseCap; the bundled wheels are missing or corrupt." `
    -Action {
        $bundled = Get-ChildItem -Path $Wheels -Filter *.whl | ForEach-Object { $_.FullName }
        if ($bundled.Count -lt 4) { throw "expected at least 4 bundled wheels in $Wheels, found $($bundled.Count)" }
        Invoke-Uv (@("pip", "install", "--python", $VenvPython) + $bundled)
    }

Step -Label "Fetch PEAR model code (pinned revision $($Manifest.pearRevision))" `
    -Fix "Check that github.com is reachable, then re-run setup." `
    -Action {
        $marker = Join-Path $PearDir "configs\infer.yaml"
        if (Test-Path $marker) {
            Write-Host "    already present -- skipping download"
            return
        }
        $zipUrl = $Manifest.pearArchiveUrl
        $zipPath = Join-Path $env:TEMP "posecap-pear-$($Manifest.pearRevision).zip"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
        $extractDir = Join-Path $env:TEMP "posecap-pear-extract-$Stamp"
        Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
        $inner = Get-ChildItem -Path $extractDir -Directory | Select-Object -First 1
        if ($null -eq $inner) { throw "PEAR archive extracted empty" }
        if (Test-Path $PearDir) { Remove-Item -Recurse -Force $PearDir }
        Move-Item -Path $inner.FullName -Destination $PearDir
        Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force $extractDir -ErrorAction SilentlyContinue
        foreach ($required in @("models", "utils", "configs\infer.yaml")) {
            if (-not (Test-Path (Join-Path $PearDir $required))) {
                throw "PEAR checkout is missing expected path '$required'"
            }
        }
    }

Step -Label "Fetch YOLO person-detection weights" `
    -Fix "Check your internet connection, then re-run setup." `
    -Action {
        $modelZoo = Join-Path $PearDir "model_zoo"
        $yolo = Join-Path $modelZoo "yolov8s.pt"
        if (Test-Path $yolo) {
            Write-Host "    already present -- skipping download"
            return
        }
        New-Item -ItemType Directory -Force -Path $modelZoo | Out-Null
        $fetch = "from ultralytics import YOLO; YOLO('yolov8s.pt')"
        Push-Location $modelZoo
        try {
            & $VenvPython -c $fetch | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "ultralytics download exited with code $LASTEXITCODE" }
        }
        finally { Pop-Location }
        if (-not (Test-Path $yolo)) { throw "yolov8s.pt did not appear in $modelZoo" }
    }

$LicensedModelsPending = $false
Step -Label "Verify install (doctor) and fetch pose-model weights (~1 GB)" `
    -Fix "Read the doctor output above -- each failing check names its own fix. Re-run setup after fixing." `
    -Action {
        $doctorOut = & $VenvPython -m posecap_engine.cli doctor --pear-root $PearDir --download-weights
        $doctorExit = $LASTEXITCODE
        $doctorOut | Out-Host
        if ($doctorExit -eq 0) { return }
        # Licensed body models (SMPL/SMPL-X/FLAME) can never be bundled or
        # auto-downloaded (ADR-0006). When they are the ONLY failing check the
        # install itself succeeded; the user finishes with a documented manual
        # download. Anything else is a real failure.
        $report = $null
        try { $report = $doctorOut | Where-Object { $_ -like '{*' } | Select-Object -Last 1 | ConvertFrom-Json } catch {}
        if ($null -eq $report) { throw "doctor reported failing checks" }
        $errors = @($report.checks | Where-Object { $_.status -eq 'error' } | ForEach-Object { $_.name })
        if ($errors.Count -ge 1 -and (@($errors | Where-Object { $_ -ne 'pear_assets' }).Count -eq 0)) {
            $script:LicensedModelsPending = $true
            return
        }
        throw "doctor reported failing checks: $($errors -join ', ')"
    }

# --- Blender extension: best effort, never fails the install -------------------
Write-Host ""
Write-Host "==> Install Blender extension (best effort)"
$extensionZip = Get-ChildItem -Path (Join-Path $InstallDir "extension") -Filter *.zip | Select-Object -First 1
$blenderCandidates = @()
$onPath = Get-Command blender -ErrorAction SilentlyContinue
if ($null -ne $onPath) { $blenderCandidates += $onPath.Source }
$blenderCandidates += Get-ChildItem "$env:ProgramFiles\Blender Foundation\Blender*\blender.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | ForEach-Object { $_.FullName }
$blender = $blenderCandidates | Select-Object -First 1
if ($null -ne $blender -and $null -ne $extensionZip) {
    & $blender --command extension install-file -r user_default -e $extensionZip.FullName | Out-Host
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    Extension installed into Blender ($blender)."
    }
    else {
        Write-Host "    Automatic install failed -- install manually: Blender > Edit > Preferences >"
        Write-Host "    Get Extensions > Install from Disk... -> $($extensionZip.FullName)"
    }
}
else {
    Write-Host "    Blender not found. Install the extension manually: Blender > Edit > Preferences >"
    Write-Host "    Get Extensions > Install from Disk... -> $(Join-Path $InstallDir 'extension')"
}

$EnginePath = Join-Path $VenvDir "Scripts\posecap-engine.exe"
Set-Content -Path (Join-Path $LogDir "SETUP_OK") -Value (Get-Date -Format "o") -Encoding ascii
Write-Host ""
Write-Host "PoseCap setup complete." -ForegroundColor Green
Write-Host "Engine executable: $EnginePath"
Write-Host "In Blender: the PoseCap panel lives in the 3D Viewport sidebar (N key)."
Write-Host "If the extension asks for the engine path, point it at the executable above."
if ($LicensedModelsPending) {
    Write-Host ""
    Write-Host "ACTION REQUIRED - licensed body models (one-time, ~5 minutes):" -ForegroundColor Yellow
    Write-Host "SMPL/SMPL-X/FLAME body models are licensed by MPI and cannot be shipped or"
    Write-Host "auto-downloaded. Register (free for research; Meshcapade for commercial use),"
    Write-Host "download, and place these files under $PearDir\assets:"
    Write-Host "  assets\SMPL\SMPL_NEUTRAL.pkl                (smpl.is.tue.mpg.de)"
    Write-Host "  assets\SMPLX\SMPLX_NEUTRAL_2020.npz         (smpl-x.is.tue.mpg.de)"
    Write-Host "  assets\SMPLX\flame_generic_model.pkl        (flame.is.tue.mpg.de)"
    Write-Host "  assets\SMPLX\smpl_mean_params.npz           (see PEAR README)"
    Write-Host "  assets\FLAME\FLAME2020\generic_model.pkl    (flame.is.tue.mpg.de)"
    Write-Host "Then run the Start Menu shortcut 'PoseCap Doctor' - all checks must be green."
}
else {
    Write-Host "SMPL-X body models are licensed separately (MPI/Meshcapade) and are NOT installed;"
    Write-Host "the extension documentation explains where to download them and where to put them."
}
Stop-Transcript | Out-Null
exit 0
