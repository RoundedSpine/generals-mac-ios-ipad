#requires -Version 5.1
<#
.SYNOPSIS
Collects base Generals archives for the Zero Hour iOS app's ZH_Generals folder.
.EXAMPLE
.\collect-ios-base-generals.ps1 -SourceDirectory 'D:\Games\Command and Conquer Generals'
#>
# GeneralsX @build Codex 25/10/2026 Keep shared base archives separate from Zero Hour's archives.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string] $SourceDirectory,
    [string] $DestinationDirectory = (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Generals-Base-iOS-Transfer')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$source = (Resolve-Path -LiteralPath $SourceDirectory).ProviderPath
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw 'Select the base Generals installation folder containing its .big files.'
}
$source = [IO.Path]::GetFullPath($source).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
$destination = [IO.Path]::GetFullPath($DestinationDirectory).TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
if ($destination.Equals($source, [StringComparison]::OrdinalIgnoreCase) -or
    $destination.StartsWith($source + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Choose an output folder outside the game installation.'
}
if (Test-Path -LiteralPath $destination) {
    throw "Output already exists: $destination. Choose a new folder; existing files will not be overwritten."
}

$archives = @(Get-ChildItem -LiteralPath $source -File | Where-Object { $_.Extension -ieq '.big' })
if ($archives.Count -eq 0) {
    throw 'No .big archives found. Select the base Generals game directory, not its saves or launcher folder.'
}
if (($archives.Name -icontains 'INIZH.big') -and -not ($archives.Name -icontains 'INI.big')) {
    throw 'This appears to be Zero Hour. Select the original base Generals installation instead.'
}
foreach ($archive in $archives) {
    if (($archive.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Linked archives are not copied automatically: $($archive.FullName)"
    }
}

# This is the exact directory the Zero Hour engine searches for shared archives.
$shared = Join-Path $destination 'ZH_Generals'
New-Item -ItemType Directory -Path $shared | Out-Null
foreach ($archive in $archives) {
    Write-Host "Copying $($archive.Name)..."
    Copy-Item -LiteralPath $archive.FullName -Destination $shared
}

$copied = @(Get-ChildItem -LiteralPath $shared -File)
$bytes = ($copied | Measure-Object -Property Length -Sum).Sum
Write-Host ''
Write-Host ("Ready: {0} archives, {1:N2} GB" -f $copied.Count, ($bytes / 1GB))
Write-Host $shared
Write-Host 'Copy the ZH_Generals FOLDER into Files > On My iPhone/iPad > Generals ZH.'
Write-Host 'The result should be Generals ZH/ZH_Generals/Textures.big (and the other base archives).'
Write-Host 'Do not put base archives directly beside the Zero Hour archives or overwrite them.'
Write-Host 'The original installation was not changed. Installed archive modifications are copied as-is.'
