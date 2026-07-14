# Shared Blender discovery for PoseCap Base install and uninstall handlers.

#Requires -Version 5.1

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

function Find-CompatibleBlenders {
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
        try {
            $versionLine = & $candidate --version 2>&1 | Select-Object -First 1
            if ($versionLine -notmatch '^Blender\s+(\d+\.\d+(?:\.\d+)?)') { continue }
            $version = [version]$Matches[1]
            if ($version -lt [version]'4.2') { continue }
            [pscustomobject]@{ Path = [string]$candidate; Version = $version }
        }
        catch { continue }
    }

    return $compatible | Sort-Object Version -Descending | Select-Object -ExpandProperty Path
}
