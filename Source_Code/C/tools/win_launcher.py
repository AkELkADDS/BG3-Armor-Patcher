"""Windows bootstrap: find/create .venv, install deps, start the GUI (no PySide6 here).

Author: AkELkA.

For a **single self-contained GUI exe** (no separate Python or repo files), use
``tools/build_launcher.ps1`` (entry ``tools/frozen_ui_entry.py``).

This script is an alternate **small** launcher that expects ``pyproject.toml`` and
``run_ui.py`` next to it and manages a local ``.venv``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

__author__ = "AkELkA"


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _console_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _pause() -> None:
    try:
        input("Press Enter to close...")
    except EOFError:
        pass


def _which_python_argv() -> list[str] | None:
    if shutil.which("py"):
        return ["py", "-3"]
    if shutil.which("python"):
        return ["python"]
    return None


def _ensure_system_python(root: Path) -> list[str] | None:
    argv = _which_python_argv()
    if argv is not None:
        return argv

    print("Python was not found.\n")
    print(
        "Trying to install Python 3 using Windows Package Manager...\n"
        "This may ask for confirmation or administrator permission.\n"
    )

    if not shutil.which("winget"):
        print('Windows Package Manager "winget" was not found.')
        print("Please install Python manually from:\nhttps://www.python.org/downloads/\n")
        print('During installation, enable "Add python.exe to PATH" and "py launcher".')
        return None

    r = subprocess.run(
        [
            "winget",
            "install",
            "--id",
            "Python.Python.3.12",
            "--source",
            "winget",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        cwd=root,
    )
    if r.returncode != 0:
        print("Automatic Python installation failed.")
        print("Please install Python manually from:\nhttps://www.python.org/downloads/")
        return None

    argv = _which_python_argv()
    if argv is not None:
        return argv

    print("Python was installed, but it is not available in this terminal yet.")
    print("Close this window and run BG3_Armor_Patcher.exe again.")
    return None


def _venv_python(root: Path) -> Path:
    return root / ".venv" / "Scripts" / "python.exe"


def _venv_pythonw(root: Path) -> Path:
    return root / ".venv" / "Scripts" / "pythonw.exe"


def _import_ok(py: Path, root: Path) -> bool:
    r = subprocess.run(
        [str(py), "-c", "import PySide6; import bg3_patcher"],
        cwd=root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_console_flags(),
    )
    return r.returncode == 0


def _install_deps(py: Path, root: Path) -> bool:
    print("Installing dependencies (first run, missing packages, or failed import check)...")
    r = subprocess.run([str(py), "-m", "pip", "install", "-q", "--upgrade", "pip"], cwd=root)
    if r.returncode != 0:
        print("Failed to update pip.")
        return False
    r = subprocess.run([str(py), "-m", "pip", "install", "-q", "-e", "."], cwd=root)
    if r.returncode != 0:
        print("Failed to install dependencies.")
        return False
    print("Done.")
    return True


def _start_gui(root: Path) -> int:
    run_script = root / "run_ui.py"
    pyw = _venv_pythonw(root)
    py = _venv_python(root)
    flags = _console_flags()
    if pyw.is_file():
        subprocess.Popen([str(pyw), str(run_script)], cwd=str(root), close_fds=True, creationflags=flags)
        return 0
    if py.is_file():
        subprocess.Popen([str(py), str(run_script)], cwd=str(root), close_fds=True, creationflags=flags)
        return 0
    print("Missing .venv Python. Re-run this launcher from the project folder.")
    return 1


def main() -> int:
    root = _project_root()
    os.chdir(root)

    if not (root / "pyproject.toml").is_file():
        print(f"pyproject.toml not found next to this launcher (expected under {root}).")
        return 1
    if not (root / "run_ui.py").is_file():
        print(f"run_ui.py not found under {root}.")
        return 1

    sys_argv = _ensure_system_python(root)
    if sys_argv is None:
        return 1

    venv_py = _venv_python(root)
    need_install = not venv_py.is_file()

    if need_install:
        print("Creating local Python environment...")
        r = subprocess.run([*sys_argv, "-m", "venv", str(root / ".venv")], cwd=root)
        if r.returncode != 0:
            print("Failed to create the Python environment.")
            return 1

    venv_py = _venv_python(root)
    if not venv_py.is_file():
        print("Failed to locate .venv Python after venv creation.")
        return 1

    force = os.environ.get("BG3_PATCHER_FORCE_PIP", "").strip()
    if force:
        print("Forcing dependency reinstall (BG3_PATCHER_FORCE_PIP is set)...")
        need_install = True

    if not need_install and not _import_ok(venv_py, root):
        need_install = True

    if need_install:
        if not _install_deps(venv_py, root):
            return 1
    else:
        print("Dependencies OK, skipping pip install.")

    return _start_gui(root)


if __name__ == "__main__":
    try:
        code = main()
    except KeyboardInterrupt:
        code = 130
    if code != 0:
        _pause()
    raise SystemExit(code)
