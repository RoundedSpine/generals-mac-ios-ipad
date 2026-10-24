#requires -Version 5.1
<#
.SYNOPSIS
Collects Zero Hour data, base Generals archives and fonts for the iOS app.
.EXAMPLE
.\collect-ios-combined-data.ps1
.EXAMPLE
.\collect-ios-combined-data.ps1 -DestinationDirectory 'D:\GeneralsZH-iOS-Complete'
#>
# GeneralsX @build Codex 25/10/2026 Collect both installations without mixing their archives.
[CmdletBinding()]
param(
    [string] $SourceDirectory = 'D:\Command and Conquer - Generals\Command and Conquer Generals Zero Hour',
    [string] $BaseGeneralsDirectory = 'D:\Command and Conquer - Generals\Command and Conquer Generals',
    [string] $DestinationDirectory = 'D:\GeneralsZH-iOS-Complete',
    [string] $FontsDirectory = (Join-Path ([Environment]::GetFolderPath('Fonts')) '.')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-FullDirectoryPath([string] $Path) {
    return [IO.Path]::GetFullPath($Path).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
}

$source = (Resolve-Path -LiteralPath $SourceDirectory).ProviderPath
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Game directory not found: $SourceDirectory"
}
$source = Get-FullDirectoryPath $source
$destination = Get-FullDirectoryPath $DestinationDirectory
if ($destination.Equals($source, [StringComparison]::OrdinalIgnoreCase) -or
    $destination.StartsWith($source + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose an output folder outside the game installation.'
}
if (Test-Path -LiteralPath $destination) {
    throw "Output already exists: $destination. Choose a new folder; existing files will not be overwritten."
}

$archives = @(Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Extension -ieq '.big' })
if ($archives.Count -eq 0) {
    throw 'No .big archives found. Select the Zero Hour installation folder, not its saves or launcher folder.'
}
# Validate the second installation before creating output or copying anything.
$base = (Resolve-Path -LiteralPath $BaseGeneralsDirectory).ProviderPath
if (-not (Test-Path -LiteralPath $base -PathType Container)) {
    throw "Base Generals directory not found: $BaseGeneralsDirectory"
}
$base = Get-FullDirectoryPath $base
if ($base.Equals($source, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Select different base Generals and Zero Hour installation folders.'
}
if ($destination.Equals($base, [StringComparison]::OrdinalIgnoreCase) -or
    $destination.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose an output folder outside both game installations.'
}
$baseArchives = @(Get-ChildItem -LiteralPath $base -File | Where-Object { $_.Extension -ieq '.big' })
if ($baseArchives.Count -eq 0) { throw 'No .big archives found in the base Generals directory.' }
if (($baseArchives.Name -icontains 'INIZH.big') -and -not ($baseArchives.Name -icontains 'INI.big')) {
    throw 'The base Generals path appears to contain Zero Hour. Check both source paths.'
}
# The explicitly selected base installation supplies ZH_Generals; do not merge
# it with an older ZH_Generals directory in the Zero Hour installation.
$folders = @(@('Data', 'Window', 'Maps') | ForEach-Object {
    $path = Join-Path $source $_
    if (Test-Path -LiteralPath $path -PathType Container) { Get-Item -LiteralPath $path }
})
$items = @($archives) + @($folders)
foreach ($item in (@($items) + @($baseArchives))) {
    if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Linked game data is not copied automatically: $($item.FullName)"
    }
    if ($item.PSIsContainer) {
        $links = @(Get-ChildItem -LiteralPath $item.FullName -Recurse -Force |
            Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 })
        if ($links.Count -gt 0) { throw "Linked files found under $($item.FullName). Use a regular local copy of the game data." }
    }
}

# Prefer already-staged game fonts, otherwise use the Windows Fonts folder.
# Accept both the engine's names and standard Windows font filenames.
$fontNames = [ordered]@{
    'arial.ttf' = @('arial.ttf')
    'arialbold.ttf' = @('arialbold.ttf', 'arialbd.ttf')
    'couriernew.ttf' = @('couriernew.ttf', 'cour.ttf')
    'timesnewroman.ttf' = @('timesnewroman.ttf', 'times.ttf')
}
$fonts = [ordered]@{}
foreach ($targetName in $fontNames.Keys) {
    foreach ($directory in @((Join-Path $source 'fonts'), $FontsDirectory)) {
        foreach ($candidate in $fontNames[$targetName]) {
            $path = Join-Path $directory $candidate
            if (Test-Path -LiteralPath $path -PathType Leaf) { $fonts[$targetName] = $path; break }
        }
        if ($fonts.Contains($targetName)) { break }
    }
    if (-not $fonts.Contains($targetName)) {
        throw "Missing font $targetName. Use -FontsDirectory to select staged fonts or your Windows Fonts folder. No output has been created."
    }
}

New-Item -ItemType Directory -Path $destination | Out-Null
foreach ($item in $items) {
    Write-Host "Copying $($item.Name)..."
    Copy-Item -LiteralPath $item.FullName -Destination $destination -Recurse
}
$shared = Join-Path $destination 'ZH_Generals'
New-Item -ItemType Directory -Path $shared | Out-Null
foreach ($archive in $baseArchives) {
    Write-Host "Copying base Generals: $($archive.Name)..."
    Copy-Item -LiteralPath $archive.FullName -Destination $shared
}
$fontDestination = Join-Path $destination 'fonts'
New-Item -ItemType Directory -Path $fontDestination | Out-Null
foreach ($targetName in $fonts.Keys) {
    Copy-Item -LiteralPath $fonts[$targetName] -Destination (Join-Path $fontDestination $targetName)
}

$copied = @(Get-ChildItem -LiteralPath $destination -Recurse -File)
$bytes = ($copied | Measure-Object -Property Length -Sum).Sum
Write-Host ''
Write-Host ("Ready: {0} files, {1:N2} GB" -f $copied.Count, ($bytes / 1GB))
Write-Host $destination
Write-Host 'Copy the CONTENTS of this folder into Files > On My iPhone/iPad > Generals ZH.'
Write-Host 'Zero Hour .big files stay at the top level; base archives stay inside ZH_Generals.'
Write-Host 'Keep the ZH_Generals and fonts folders intact. Do not add an extra enclosing folder.'
Write-Host 'Original game files were not changed. Windows executables, DLLs and installers were not selected.'
