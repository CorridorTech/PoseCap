# PoseCap installed-component inventory and safe deselection cleanup (task 0022).
# This script is intentionally independent of Blender, Python, CUDA, and network
# access so its lifecycle behavior can be verified against temporary directories.

#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDir,
    [Parameter(Mandatory = $true)] [ValidateSet("Begin", "BaseReady", "Complete")] [string]$Action,
    [Parameter(Mandatory = $true)] [string]$Components,
    [Parameter(Mandatory = $true)] [string]$Version
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$InventoryPath = Join-Path $InstallDir "installed_components.json"
$InventoryTempPath = "$InventoryPath.tmp"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Get-SelectedComponents {
    $selected = @($Components.Split(','))
    $canonical = $selected -join ','
    if ($canonical -notin @("base", "base,mediapipe", "base,pear", "base,mediapipe,pear")) {
        throw "invalid component selection '$Components'"
    }
    return $selected
}

function Get-PayloadProvenance {
    param([Parameter(Mandatory = $true)] [string]$Component)
    $payloadManifestPath = Join-Path $InstallDir "$Component`_payload_manifest.json"
    try {
        $payloadManifest = Get-Content `
            -LiteralPath $payloadManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $payloadArchive = $payloadManifest.archive
        $provenance = [ordered]@{
            manifest_path = "$Component`_payload_manifest.json"
            filename = [string]$payloadArchive.filename
            url = [string]$payloadArchive.url
            sha256 = [string]$payloadArchive.sha256
            size_bytes = [long]$payloadArchive.size_bytes
        }
        if ($Component -eq "mediapipe") {
            $provenance.model = [ordered]@{
                filename = [string]$payloadManifest.model.filename
                url = [string]$payloadManifest.model.url
                sha256 = [string]$payloadManifest.model.sha256
                size_bytes = [long]$payloadManifest.model.size_bytes
            }
        }
        return $provenance
    }
    catch {
        throw "invalid $Component payload manifest at '$payloadManifestPath': $($_.Exception.Message)"
    }
}

function Read-InstalledInventory {
    if (-not (Test-Path -LiteralPath $InventoryPath -PathType Leaf)) {
        return $null
    }
    try {
        $inventory = Get-Content -LiteralPath $InventoryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "malformed installed component inventory at '$InventoryPath': $($_.Exception.Message)"
    }
    if ($null -eq $inventory -or $inventory.schema_version -ne 1 -or $null -eq $inventory.components) {
        throw "malformed installed component inventory at '$InventoryPath': unsupported schema"
    }
    return $inventory
}

function Write-InstalledInventory {
    param([Parameter(Mandatory = $true)] [object]$Inventory)
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    $json = $Inventory | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($InventoryTempPath, $json, $Utf8NoBom)
    Move-Item -Force -LiteralPath $InventoryTempPath -Destination $InventoryPath
}

function Test-InventoryHasComponent {
    param([object]$Inventory, [string]$Name)
    if ($null -eq $Inventory) { return $false }
    return @($Inventory.components.PSObject.Properties.Name) -contains $Name
}

function Remove-InstallerOwnedTree {
    param([Parameter(Mandatory = $true)] [string]$RelativePath)
    $root = [System.IO.Path]::GetFullPath($InstallDir).TrimEnd('\', '/')
    $target = [System.IO.Path]::GetFullPath((Join-Path $root $RelativePath))
    $rootPrefix = $root + [System.IO.Path]::DirectorySeparatorChar
    if (-not $target.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "refusing to remove path outside the PoseCap install root: '$target'"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -Recurse -Force -LiteralPath $target
    }
}

try {
    $selected = Get-SelectedComponents
    $previous = Read-InstalledInventory

    if ($Action -eq "Begin") {
        $previousVersion = $null
        if ($null -ne $previous) { $previousVersion = [string]$previous.version }

        $pearPayloadProvenance = $null
        if ($selected -contains "pear") {
            $pearPayloadProvenance = Get-PayloadProvenance -Component "pear"
        }
        $mediapipePayloadProvenance = $null
        if ($selected -contains "mediapipe") {
            $mediapipePayloadProvenance = Get-PayloadProvenance -Component "mediapipe"
        }

        $componentInventory = [ordered]@{
            base = [ordered]@{
                version = $Version
                state = "installing"
                owned_paths = @(
                    "bootstrap",
                    "extension",
                    "installer_manifest.json",
                    "pear_payload_manifest.json",
                    "mediapipe_payload_manifest.json",
                    "installed_components.json",
                    "LICENSE",
                    "THIRD_PARTY_NOTICES.md"
                )
                manifest = [ordered]@{ state = "not_applicable"; path = $null }
            }
        }
        if ($selected -contains "mediapipe") {
            $componentInventory.mediapipe = [ordered]@{
                version = $Version
                state = "installing"
                owned_paths = @("payloads/mediapipe", "backends/mediapipe")
                manifest = [ordered]@{ state = "pending"; path = "backends/mediapipe/backend.json" }
                payload = $mediapipePayloadProvenance
            }
        }
        if ($selected -contains "pear") {
            $componentInventory.pear = [ordered]@{
                version = $Version
                state = "installing"
                owned_paths = @(
                    "bin",
                    "wheels",
                    "requirements-torch.lock",
                    "requirements-pypi.lock",
                    "payloads/pear",
                    "python",
                    "runtime",
                    "backends/pear"
                )
                retained_data_paths = @("pear")
                manifest = [ordered]@{ state = "pending"; path = "backends/pear/backend.json" }
                payload = $pearPayloadProvenance
            }
        }

        $installing = [ordered]@{
            schema_version = 1
            version = $Version
            transaction_state = "installing"
            previous_version = $previousVersion
            components = $componentInventory
        }
        Write-InstalledInventory -Inventory $installing

        $legacyPearManifest = Join-Path $InstallDir "backends\pear\backend.json"
        $legacyPearEngine = Join-Path $InstallDir "runtime\venv\Scripts\posecap-engine.exe"
        $previouslyHadPear = (Test-InventoryHasComponent -Inventory $previous -Name "pear") -or
            (Test-Path -LiteralPath $legacyPearManifest -PathType Leaf) -or
            (Test-Path -LiteralPath $legacyPearEngine -PathType Leaf)
        if ($previouslyHadPear -and -not ($selected -contains "pear")) {
            # The separately licensed/user-acquired PEAR data tree is retained.
            foreach ($ownedPath in @(
                "bin",
                "wheels",
                "requirements-torch.lock",
                "requirements-pypi.lock",
                "payloads\pear",
                "runtime",
                "python",
                "backends\pear"
            )) {
                Remove-InstallerOwnedTree -RelativePath $ownedPath
            }
        }
        $legacyMediaPipeManifest = Join-Path $InstallDir "backends\mediapipe\backend.json"
        $previouslyHadMediaPipe = (Test-InventoryHasComponent -Inventory $previous -Name "mediapipe") -or
            (Test-Path -LiteralPath $legacyMediaPipeManifest -PathType Leaf)
        if ($previouslyHadMediaPipe -and -not ($selected -contains "mediapipe")) {
            foreach ($ownedPath in @("payloads\mediapipe", "backends\mediapipe")) {
                Remove-InstallerOwnedTree -RelativePath $ownedPath
            }
        }
        return
    }

    if ($null -eq $previous -or $previous.transaction_state -ne "installing") {
        throw "cannot complete component lifecycle without an installing inventory"
    }
    $recordedNames = @($previous.components.PSObject.Properties.Name)
    if (($recordedNames -join ',') -ne ($selected -join ',')) {
        throw "component selection changed during installation"
    }
    if ($Action -eq "BaseReady") {
        $previous.components.base.state = "ready"
        Write-InstalledInventory -Inventory $previous
        return
    }
    foreach ($name in $selected | Where-Object { $_ -ne "base" }) {
        $backendManifest = Join-Path $InstallDir "backends\$name\backend.json"
        if (-not (Test-Path -LiteralPath $backendManifest -PathType Leaf)) {
            throw "$name was selected but its backend manifest is missing"
        }
        $previous.components.$name.manifest.state = "registered"
    }
    foreach ($name in $recordedNames) {
        $previous.components.$name.state = "ready"
    }
    $previous.transaction_state = "ready"
    $previous.PSObject.Properties.Remove("previous_version")
    Write-InstalledInventory -Inventory $previous
    return
}
catch {
    throw
}
