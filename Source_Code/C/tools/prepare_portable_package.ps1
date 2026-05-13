# BG3 Armor Patcher — Author: AkELkA
# Copies build output into BG3_Armor_Patcher_Package for zipping.
# - one-file build: copies BG3_Armor_Patcher.exe only
# - onedir build: copies the whole BG3_Armor_Patcher folder (exe + _internal)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $root "BG3_Armor_Patcher_Package"
$onefile = Join-Path $root "BG3_Armor_Patcher.exe"
$onedir = Join-Path $root "BG3_Armor_Patcher"

if (Test-Path $dst) {
    Remove-Item $dst -Recurse -Force
}
New-Item -ItemType Directory -Path $dst -Force | Out-Null

if (Test-Path $onefile) {
    Copy-Item $onefile $dst -Force
    Write-Host "Done: $dst\BG3_Armor_Patcher.exe (zip this folder — one exe)"
    exit 0
}

$onedirExe = Join-Path $onedir "BG3_Armor_Patcher.exe"
if (Test-Path $onedirExe) {
    Copy-Item $onedir (Join-Path $dst "BG3_Armor_Patcher") -Recurse -Force
    Write-Host "Done: $dst\BG3_Armor_Patcher\ (zip this folder — include _internal)"
    exit 0
}

throw "No build found. Run:  powershell -File tools\build_launcher.ps1   or   ... -Layout onedir"
