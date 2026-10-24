#requires -Version 5.1
<#
.SYNOPSIS
Copies Zero Hour data and fonts into a folder ready to transfer to the iOS app.
.EXAMPLE
.\collect-ios-game-data.ps1
.EXAMPLE
.\collect-ios-game-data.ps1 -DestinationDirectory 'D:\GeneralsZH-iOS-Transfer'
#>
# GeneralsX @build Codex 24/10/2026 Stage retail assets without modifying the installation.
[CmdletBinding()]
param(
    [string] $SourceDirectory = 'D:\Command & Conquer Generals Zero Hour',
    [string] $DestinationDirectory = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'GeneralsZH-iOS-Transfer'),
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
$folders = @(@('Data', 'Window', 'Maps', 'ZH_Generals') | ForEach-Object {
    $path = Join-Path $source $_
    if (Test-Path -LiteralPath $path -PathType Container) { Get-Item -LiteralPath $path }
})
$items = @($archives) + @($folders)
foreach ($item in $items) {
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
Write-Host 'Keep .big files directly at that level, without an extra enclosing folder.'
Write-Host 'Original game files were not changed. Windows executables, DLLs and installers were not selected.'
