# Shared Blender discovery for PoseCap Base install and uninstall handlers.

#Requires -Version 5.1
. (Join-Path $PSScriptRoot "native_command.ps1")

function Get-SteamInstallRoots {
    $roots = @()
    foreach ($registryPath in @(
        'HKCU:\Software\Valve\Steam',
        'HKLM:\Software\Valve\Steam',
        'HKLM:\Software\WOW6432Node\Valve\Steam'
    )) {
        $steam = Get-ItemProperty -Path $registryPath -ErrorAction SilentlyContinue
        if ($null -eq $steam) { continue }

        foreach ($propertyName in @('SteamPath', 'InstallPath')) {
            $property = $steam.PSObject.Properties[$propertyName]
            if ($null -ne $property -and -not [string]::IsNullOrWhiteSpace($property.Value)) {
                $roots += [string]$property.Value
            }
        }
    }

    foreach ($programFiles in @($env:ProgramFiles, ${env:ProgramFiles(x86)})) {
        if (-not [string]::IsNullOrWhiteSpace($programFiles)) {
            $roots += Join-Path $programFiles 'Steam'
        }
    }

    return $roots | Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
        Select-Object -Unique
}

function Get-SteamLibraryRoots {
    param([Parameter(Mandatory = $true)] [string]$SteamRoot)

    $libraries = @($SteamRoot)
    $libraryFolders = Join-Path $SteamRoot 'steamapps\libraryfolders.vdf'
    if (Test-Path -LiteralPath $libraryFolders -PathType Leaf) {
        try {
            $contents = Get-Content -LiteralPath $libraryFolders -Raw -ErrorAction Stop
            foreach ($match in [regex]::Matches($contents, '"path"\s*"([^"]+)"')) {
                $libraries += $match.Groups[1].Value -replace '\\\\', '\'
            }
        }
        catch {
            Write-Warning "Steam library metadata could not be read at $libraryFolders."
        }
    }

    return $libraries | Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
        Select-Object -Unique
}

function Get-BlenderVersion {
    # Not Mandatory: the parameter binder would reject an empty string with a
    # terminating error before the body runs; an empty path must instead
    # return $null like every other non-Blender input.
    param([string]$Path = "")
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        $outputLines = @(Invoke-NativeCommand -FilePath $Path -ArgumentList @('--version'))
        $versionLine = @($outputLines) -match '^Blender\s' | Select-Object -First 1
        if ($null -eq $versionLine) { return $null }
        if ($versionLine -notmatch '^Blender\s+(\d+\.\d+(?:\.\d+)?)') { return $null }
        return [version]$Matches[1]
    }
    catch { return $null }
}

function Get-BlenderOverridePath {
    # The manual path the user picked in the setup wizard (task 0030). It is
    # candidate input only: it passes the same version gate as every
    # discovered Blender, and a stale or invalid override simply falls
    # through to automatic discovery.
    param([string]$InstallDir = "")
    if ([string]::IsNullOrWhiteSpace($InstallDir)) { return $null }
    $overrideFile = Join-Path $InstallDir "blender_override.txt"
    if (-not (Test-Path -LiteralPath $overrideFile -PathType Leaf)) { return $null }
    $fileContents = Get-Content -LiteralPath $overrideFile -Raw
    if ([string]::IsNullOrWhiteSpace($fileContents)) { return $null }
    return $fileContents.Trim()
}

function Find-CompatibleBlenders {
    param([string]$InstallDir = "")
    $candidates = @()
    $onPath = Get-Command blender -ErrorAction SilentlyContinue
    if ($null -ne $onPath) { $candidates += $onPath.Source }

    $candidates += Get-ChildItem `
        "$env:ProgramFiles\Blender Foundation\Blender*\blender.exe" `
        -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        ForEach-Object { $_.FullName }

    foreach ($steamRoot in @(Get-SteamInstallRoots)) {
        foreach ($libraryRoot in @(Get-SteamLibraryRoots -SteamRoot $steamRoot)) {
            $steamBlender = Join-Path $libraryRoot 'steamapps\common\Blender\blender.exe'
            if (Test-Path -LiteralPath $steamBlender -PathType Leaf) {
                $candidates += $steamBlender
            }
        }
    }

    $compatible = foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $version = Get-BlenderVersion -Path $candidate
        if ($null -eq $version -or $version -lt [version]'4.2') { continue }
        [pscustomobject]@{ Path = [string]$candidate; Version = $version }
    }
    $discovered = @($compatible | Sort-Object Version -Descending |
        Select-Object -ExpandProperty Path)

    # A compatible user-chosen override outranks discovered installs; the
    # user picked it deliberately.
    $overridePath = Get-BlenderOverridePath -InstallDir $InstallDir
    if ($null -ne $overridePath) {
        $overrideVersion = Get-BlenderVersion -Path $overridePath
        if ($null -ne $overrideVersion -and $overrideVersion -ge [version]'4.2') {
            return @($overridePath) + @($discovered | Where-Object { $_ -ne $overridePath })
        }
    }
    return $discovered
}
