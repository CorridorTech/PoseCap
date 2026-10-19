# PEAR runtime selection shared by install_pear.ps1 and switch_pear_runtime.ps1
# (ADR-0019). cu128 is the default for every GPU; cu124 is the opt-in matrix
# that restores pre-Blackwell throughput. The choice lives in pear_runtime.json
# so upgrades and repairs reinstall the runtime the user picked.

#Requires -Version 5.1

$PearDefaultRuntime = "cu128"
$PearLegacyRuntime = "cu124"
$PearLegacyIndexUrl = "https://download.pytorch.org/whl/cu124"

function Get-PearRuntimePreferencePath {
    param([Parameter(Mandatory = $true)] [string]$InstallDir)
    Join-Path $InstallDir "pear_runtime.json"
}

function Get-PearRuntimeSelection {
    param([Parameter(Mandatory = $true)] [string]$InstallDir)
    $path = Get-PearRuntimePreferencePath -InstallDir $InstallDir
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $PearDefaultRuntime }
    $runtime = [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json).runtime
    if (@($PearDefaultRuntime, $PearLegacyRuntime) -notcontains $runtime) {
        throw "pear_runtime.json names unknown runtime '$runtime'; expected $PearDefaultRuntime or $PearLegacyRuntime"
    }
    return $runtime
}

function Set-PearRuntimeSelection {
    param(
        [Parameter(Mandatory = $true)] [string]$InstallDir,
        [Parameter(Mandatory = $true)] [ValidateSet("cu128", "cu124")] [string]$Runtime
    )
    $path = Get-PearRuntimePreferencePath -InstallDir $InstallDir
    if ($Runtime -eq $PearDefaultRuntime) {
        # The default is the absence of a preference, so a reset leaves no trace.
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
        return
    }
    [ordered]@{ runtime = $Runtime } | ConvertTo-Json |
        Set-Content -LiteralPath $path -Encoding UTF8
}

function Get-PearRuntimeSpec {
    # Where the torch pins, their index, and the matching PyTorch3D wheel come
    # from. A PyTorch3D build only loads under the torch it was compiled
    # against, so the three always travel together.
    param(
        [Parameter(Mandatory = $true)] [string]$InstallDir,
        [Parameter(Mandatory = $true)] [string]$Runtime,
        [Parameter(Mandatory = $true)] [string]$DefaultIndexUrl
    )
    if ($Runtime -ne $PearLegacyRuntime) {
        return @{
            Runtime = $PearDefaultRuntime
            IndexUrl = $DefaultIndexUrl
            LockPath = Join-Path $InstallDir "requirements-torch.lock"
            Pytorch3dWheel = $null
        }
    }
    $lockPath = Join-Path $InstallDir "requirements-torch-cu124.lock"
    $wheels = @(Get-ChildItem -Path (Join-Path $InstallDir "wheels\cu124") -Filter "pytorch3d-*.whl" `
            -ErrorAction SilentlyContinue)
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf) -or $wheels.Count -ne 1) {
        throw "this PEAR payload does not include the CUDA 12.4 runtime; update PoseCap or switch back to the default runtime"
    }
    return @{
        Runtime = $PearLegacyRuntime
        IndexUrl = $PearLegacyIndexUrl
        LockPath = $lockPath
        Pytorch3dWheel = $wheels[0].FullName
    }
}

function Get-PearLegacyBlockingGpus {
    # GPUs the cu124 matrix cannot drive: its kernels end at sm_90, so RTX 50
    # (Blackwell, compute capability 10.x/12.x) needs cu128. Returns the GPU
    # names; empty when every GPU is fine or nvidia-smi cannot answer (the
    # doctor gate still checks compiled architectures after install).
    param([string[]]$SmiOutput)
    $blocking = @()
    foreach ($line in $SmiOutput) {
        $fields = @($line.Split(",") | ForEach-Object { $_.Trim() })
        if ($fields.Count -lt 2) { continue }
        $capability = $fields[$fields.Count - 1]
        if ($capability -notmatch '^(\d+)\.\d+$') { continue }
        if ([int]$Matches[1] -ge 10) {
            $blocking += ($fields[0..($fields.Count - 2)] -join ",")
        }
    }
    return $blocking
}

function Read-NvidiaGpuCapabilities {
    $smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if ($null -eq $smi) { return @() }
    $output = @(Invoke-NativeCommand -FilePath $smi.Source -ArgumentList @(
            "--query-gpu=name,compute_cap", "--format=csv,noheader"))
    if ($LASTEXITCODE -ne 0) { return @() }
    return $output
}
