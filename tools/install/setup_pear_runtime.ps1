#Requires -Version 5.1

[CmdletBinding()]
param(
    [ValidateSet("12.4")]
    [string]$Cuda = "12.4",

    [string]$PearRoot = "C:\Dev\PoseCap-PEAR",

    [string]$VenvPath = ".venv-pear",

    [string]$CudaHome = "",

    [string]$Pytorch3DRef = "v0.7.9",

    [string]$Pytorch3DSourcePath = ".agentic\p3d",

    [switch]$SkipPytorch3D
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$LogRoot = Join-Path $RepoRoot ".agentic\pear-runtime"
$Stamp = Get-Date -Format "yyyyMMddTHHmmss"
$LogPath = Join-Path $LogRoot ("setup-pear-runtime-cu{0}-{1}.log" -f ($Cuda -replace "\.", ""), $Stamp)

function Resolve-TargetPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $RepoRoot $PathValue
}

function Invoke-Logged {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Command,
        [switch]$AllowFailure
    )

    Write-Host ""
    Write-Host "==> $Label"
    Write-Host ("    " + ($Command -join " "))

    $Program = $Command[0]
    $Arguments = @()
    if ($Command.Count -gt 1) {
        $Arguments = $Command[1..($Command.Count - 1)]
    }

    & $Program @Arguments
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -eq 0) {
        return
    }

    $Message = "$Label exited with code $ExitCode. See $LogPath."
    if ($AllowFailure) {
        Write-Warning $Message
        return
    }
    throw $Message
}

function Assert-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$InstallHint
    )

    if (Get-Command $Name -ErrorAction SilentlyContinue) {
        return
    }
    throw "$Name was not found. $InstallHint"
}

function Assert-Directory {
    param(
        [Parameter(Mandatory = $true)][string]$PathValue,
        [Parameter(Mandatory = $true)][string]$FailureMessage
    )

    if (Test-Path -LiteralPath $PathValue -PathType Container) {
        return
    }
    throw $FailureMessage
}

$TorchIndexes = @{
    "12.4" = "https://download.pytorch.org/whl/cu124"
}

$VenvFullPath = Resolve-TargetPath $VenvPath
$PythonExe = Join-Path $VenvFullPath "Scripts\python.exe"
$PearRootFullPath = Resolve-TargetPath $PearRoot

if ($CudaHome.Trim() -eq "") {
    $CudaHome = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8"
}
$CudaHomeFullPath = Resolve-TargetPath $CudaHome
$Pytorch3DSourceFullPath = Resolve-TargetPath $Pytorch3DSourcePath

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
Start-Transcript -Path $LogPath -Force | Out-Null

$ScriptFailed = $false

try {
    if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
        throw "Task 0007 validates the Windows PEAR runtime; run this script on Windows."
    }

    Assert-Command -Name "uv" -InstallHint "Install uv before running the PEAR runtime setup."
    Assert-Command -Name "git" -InstallHint "Install git before running the PEAR runtime setup."
    Assert-Directory `
        -PathValue $PearRootFullPath `
        -FailureMessage "PEAR checkout not found at $PearRootFullPath. Clone the pinned external checkout there; do not copy files from CorridorRig-Original."

    if (-not $SkipPytorch3D) {
        Assert-Command `
            -Name "cl.exe" `
            -InstallHint "Run this script from a Developer PowerShell for VS 2022 so PyTorch3D can compile."
        Assert-Directory `
            -PathValue $CudaHomeFullPath `
            -FailureMessage "CUDA Toolkit path not found at $CudaHomeFullPath. Install the CUDA Toolkit there or pass -CudaHome to an installed toolkit compatible with the Torch CUDA $Cuda wheel matrix."
    }

    Write-Host "PoseCap root: $RepoRoot"
    Write-Host "PEAR root: $PearRootFullPath"
    Write-Host "Runtime venv: $VenvFullPath"
    Write-Host "Torch CUDA wheel matrix: $Cuda"
    Write-Host "CUDA toolkit: $CudaHomeFullPath"
    Write-Host "PyTorch3D source: $Pytorch3DSourceFullPath"
    Write-Host "Log: $LogPath"

    if (Test-Path -LiteralPath $PythonExe -PathType Leaf) {
        Write-Host ""
        Write-Host "==> Reuse existing Python runtime venv"
        Write-Host "    $PythonExe"
    }
    else {
        Invoke-Logged `
            -Label "Create Python 3.11 uv virtual environment" `
            -Command @("uv", "venv", "--python", "3.11", $VenvFullPath)
    }

    Invoke-Logged `
        -Label "Install PoseCap workspace packages into runtime venv" `
        -Command @(
            "uv", "pip", "install", "--python", $PythonExe,
            "-e", (Join-Path $RepoRoot "contracts"),
            "-e", (Join-Path $RepoRoot "core"),
            "-e", (Join-Path $RepoRoot "engine")
        )

    Invoke-Logged `
        -Label "Install Torch/Torchvision CUDA $Cuda wheel matrix" `
        -Command @(
            "uv", "pip", "install", "--python", $PythonExe,
            "--index-url", $TorchIndexes[$Cuda],
            "torch==2.4.1",
            "torchvision==0.19.1"
        )

    # PEAR's requirements file pins an older Torch stack, so task 0007 owns this curated set.
    Invoke-Logged `
        -Label "Install PEAR Python dependencies that do not define the Torch matrix" `
        -Command @(
            "uv", "pip", "install", "--python", $PythonExe,
            "setuptools",
            "wheel",
            "ultralytics",
            "huggingface_hub",
            "lightning",
            "timm",
            "omegaconf",
            "roma",
            "einops",
            "colored",
            "rich",
            "trimesh",
            "plotly",
            "smplx",
            "fvcore",
            "iopath",
            "ninja"
        )

    if (-not $SkipPytorch3D) {
        $env:DISTUTILS_USE_SDK = "1"
        $env:CUDA_HOME = $CudaHomeFullPath
        $env:CUB_HOME = Join-Path $CudaHomeFullPath "include"
        $env:MAX_JOBS = "1"

        if (Test-Path -LiteralPath $Pytorch3DSourceFullPath -PathType Container) {
            Invoke-Logged `
                -Label "Update local PyTorch3D source checkout" `
                -Command @("git", "-C", $Pytorch3DSourceFullPath, "fetch", "--tags", "origin")
            Invoke-Logged `
                -Label "Checkout PyTorch3D $Pytorch3DRef" `
                -Command @("git", "-C", $Pytorch3DSourceFullPath, "checkout", $Pytorch3DRef)
        }
        else {
            Invoke-Logged `
                -Label "Clone PyTorch3D $Pytorch3DRef source" `
                -Command @(
                    "git", "clone", "--branch", $Pytorch3DRef, "--depth", "1",
                    "https://github.com/facebookresearch/pytorch3d.git",
                    $Pytorch3DSourceFullPath
                )
        }

        Invoke-Logged `
            -Label "Build and install PyTorch3D $Pytorch3DRef from source" `
            -Command @(
                "uv", "pip", "install", "--python", $PythonExe,
                $Pytorch3DSourceFullPath,
                "--no-build-isolation"
            )
    }

    Invoke-Logged `
        -Label "Run PEAR runtime doctor" `
        -Command @(
            $PythonExe, "-m", "posecap_engine.cli", "doctor",
            "--pear-root", $PearRootFullPath,
            "--download-weights"
        ) `
        -AllowFailure

    Write-Host ""
    Write-Host "PEAR runtime setup finished. Review $LogPath and the doctor JSON before marking task 0007 checks."
}
catch {
    $ScriptFailed = $true
    Write-Host ""
    Write-Host ("ERROR: " + $_.Exception.Message)
    Write-Host "Log: $LogPath"
}
finally {
    Stop-Transcript | Out-Null
}

if ($ScriptFailed) {
    exit 1
}
