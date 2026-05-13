# BG3 Armor Patcher

**Author:** AkELkA

## License

This project is released under **[CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)** (public domain dedication): you may use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, for any purpose, without owing royalties or attribution (see the full `LICENSE` file for the exact legal terms, waivers, and limitations—including that **trademark and patent rights are not waived**).

**Fully free:** CC0 is the most permissive Creative Commons option—copyright and related rights are waived worldwide where the law allows, with a fallback license that grants the same freedoms if a waiver is not recognized in your jurisdiction.

Python tool for generating Baldur's Gate 3 armor patch files from unpacked vanilla data and unpacked mods.

Version 1 works with `.lsx` files only. If root template `.lsf` files are found without converted `.lsx` files, the program stops and tells the user to convert them manually.

## Start On Windows

Double-click **`BG3_Armor_Patcher.exe`** in the project folder. It embeds `favicon.ico`, so Explorer and the taskbar show your icon without shortcuts or extra steps. Behavior matches the old batch launcher: it looks for Python (and can install Python 3.12 via `winget` if needed), creates a local `.venv`, runs `pip install` only on first run or when imports fail, then starts the GUI with `pythonw` so the console closes after setup.

Keep **`favicon.ico`** in the project root for the in-app window icon (the `.exe` already carries the same icon in its resources).

To force a full `pip install` again, set the environment variable `BG3_PATCHER_FORCE_PIP` to any value before starting the launcher.

If you do not have the `.exe` (for example you cloned source only), build it once after creating `.venv` and installing the project:

```powershell
pip install -e ".[launcher]"
powershell -ExecutionPolicy Bypass -File .\tools\build_launcher.ps1
```

Fallback without PyInstaller: **`BG3_Armor_Patcher.bat`** does the same setup; batch files cannot show a custom Explorer icon on Windows.

If automatic Python installation fails, install Python from https://www.python.org/downloads/ and run the launcher again.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

Run the UI:

```powershell
bg3-armor-patcher-ui
```

Run the command-line patcher with a saved preset:

```powershell
bg3-armor-patcher path\to\preset.json
```
