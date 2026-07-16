# PoseCap wizard-time Blender probe (task 0030).
#
# Two modes, both exiting 0 for "usable Blender" and 1 otherwise:
#   (no arguments)              -- can automatic discovery find Blender 4.2+?
#   -CandidatePath <blender.exe> -- is this specific file a Blender 4.2+?
# The setup wizard uses the first to decide whether to show the manual-path
# page and the second to validate what the user picked, so the wizard and the
# install handlers share one validation policy (blender_discovery.ps1).

#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$CandidatePath = "",
    [string]$InstallDir = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
. (Join-Path $PSScriptRoot "native_command.ps1")
. (Join-Path $PSScriptRoot "blender_discovery.ps1")

if ($CandidatePath -ne "") {
    $version = Get-BlenderVersion -Path $CandidatePath
    if ($null -ne $version -and $version -ge [version]'4.2') { exit 0 }
    exit 1
}

if (@(Find-CompatibleBlenders -InstallDir $InstallDir).Count -gt 0) { exit 0 }
exit 1
