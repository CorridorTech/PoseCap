# PoseCap Base uninstall handler.

#Requires -Version 5.1
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "blender_discovery.ps1")

try {
    $blenders = @(Find-CompatibleBlenders)
    if ($blenders.Count -eq 0) {
        Write-Warning "Blender 4.2 or newer was not found; extension cleanup was skipped."
        exit 0
    }

    $extensionListArguments = @("--command", "extension", "list")
    foreach ($blender in $blenders) {
        $extensionList = Invoke-NativeCommand -FilePath $blender -ArgumentList $extensionListArguments
        if ($LASTEXITCODE -ne 0) { throw "Blender could not list installed extensions" }
        if (-not ($extensionList -match '(?m)^\s*posecap\s+\[installed\]')) {
            continue
        }

        & $blender --command extension remove posecap | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Blender could not remove the PoseCap extension" }
        $afterRemoval = Invoke-NativeCommand -FilePath $blender -ArgumentList $extensionListArguments
        if ($LASTEXITCODE -ne 0) { throw "Blender could not verify extension removal" }
        if ($afterRemoval -match '(?m)^\s*posecap\s+\[installed\]') {
            throw "Blender still reports PoseCap as installed"
        }
    }
    Write-Host "PoseCap Blender extension cleanup complete."
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}

exit 0
