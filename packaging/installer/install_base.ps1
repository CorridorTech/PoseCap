# PoseCap Base component handler (task 0022).

#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDir
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "blender_discovery.ps1")

function Invoke-BaseStep {
    param([string]$Label, [scriptblock]$Action, [string]$Fix)
    Write-Host ""
    Write-Host "==> $Label"
    try { & $Action }
    catch { throw "$Label -- $($_.Exception.Message). How to fix: $Fix" }
}

Invoke-BaseStep -Label "Install and verify the Blender extension" `
    -Fix "Install Blender 4.2 or newer, close Blender, and run PoseCap Setup (repair)." `
    -Action {
        $extensionZip = Get-ChildItem -Path (Join-Path $InstallDir "extension") -Filter *.zip |
            Select-Object -First 1
        if ($null -eq $extensionZip) {
            throw "the PoseCap Blender extension package is missing"
        }

        $blender = @(Find-CompatibleBlenders) | Select-Object -First 1
        if ($null -eq $blender) { throw "Blender 4.2 or newer was not found" }

        $extensionListArguments = @("--command", "extension", "list")
        $installedExtensions = Invoke-NativeCommand -FilePath $blender -ArgumentList $extensionListArguments
        $installedExtensions | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Blender could not list installed extensions" }
        if ($installedExtensions -match '(?m)^\s*posecap\s+\[installed\]') {
            Invoke-NativeCommand -FilePath $blender `
                -ArgumentList @("--command", "extension", "remove", "posecap") | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Blender could not remove the previous PoseCap extension" }
        }

        & $blender --command extension install-file -r user_default -e $extensionZip.FullName | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "Blender could not install the PoseCap extension" }
        $extensionList = Invoke-NativeCommand -FilePath $blender -ArgumentList $extensionListArguments
        $extensionList | Out-Host
        if ($LASTEXITCODE -ne 0 -or -not ($extensionList -match '(?m)^\s*posecap\s+\[installed\]')) {
            throw "Blender did not report PoseCap as installed"
        }
        Write-Host "    PoseCap Base is installed and enabled in Blender."
    }
