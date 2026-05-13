# BG3 Armor Patcher - Author: AkELkA
# Builds the frozen GUI via PyInstaller.
#
# Frozen exe ships with no preset JSON inside (users add presets next to the exe if they want).
#
# Default is --onefile (single .exe). Startup is much faster than --collect-all PySide6
# (only Qt modules your code imports are bundled; ~tens of MB instead of hundreds).
#
# For fastest cold start, use:  powershell -File tools\build_launcher.ps1 -Layout onedir
# (zip the whole BG3_Armor_Patcher folder next to the .exe - not a single file, but quickest.)
param(
    [ValidateSet("onefile", "onedir")]
    [string]$Layout = "onefile"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "favicon.ico")) {
    throw "favicon.ico must exist in project root."
}
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Create .venv first (e.g. python -m venv .venv then pip install -e .)."
}

$py = Join-Path $root ".venv\Scripts\python.exe"
& $py -m pip install -q "pyinstaller>=6"

$work = Join-Path $root "build\pyinstaller"
if (Test-Path $work) {
    Remove-Item -Recurse -Force $work
}
New-Item -ItemType Directory -Path $work -Force | Out-Null

$icon = Join-Path $root "favicon.ico"
$entry = Join-Path $root "tools\frozen_ui_entry.py"
$src = Join-Path $root "src"

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--noconsole",
    "--noupx",
    "--name", "BG3_Armor_Patcher",
    "--icon", $icon,
    "--paths", $src,
    "--add-data", "$icon;.",
    "--distpath", $root,
    "--workpath", $work,
    "--specpath", $work,
    $entry
)
if ($Layout -eq "onefile") {
    $pyiArgs = @("--onefile") + $pyiArgs
} else {
    $pyiArgs = @("--onedir") + $pyiArgs
}

& $py -m PyInstaller @pyiArgs

if ($Layout -eq "onefile") {
    $exe = Join-Path $root "BG3_Armor_Patcher.exe"
    if (-not (Test-Path $exe)) {
        throw "PyInstaller did not produce BG3_Armor_Patcher.exe"
    }
    Write-Host "Built (one-file GUI, slim Qt bundle): $exe"
} else {
    $exe = Join-Path $root "BG3_Armor_Patcher\BG3_Armor_Patcher.exe"
    if (-not (Test-Path $exe)) {
        throw "PyInstaller did not produce folder BG3_Armor_Patcher"
    }
    Write-Host "Built (onedir, fastest startup - zip the whole BG3_Armor_Patcher folder): $exe"
}
