#!/usr/bin/env python3
"""Start the UI using this folder's ``src/bg3_patcher`` only.

Run from the project root (same folder as this file):

  python run_ui.py

If you still see an old UI, another ``bg3_patcher`` install is winning. Run::

  pip uninstall bg3-armor-patcher

(or uninstall any editable install from an old folder), then use ``python run_ui.py`` again.

Author: AkELkA.
"""
from __future__ import annotations

__author__ = "AkELkA"

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    src = root / "src"
    pkg = src / "bg3_patcher"
    if not pkg.is_dir():
        print(f"Cannot find package at {pkg}", file=sys.stderr)
        return 1

    src_resolved = src.resolve()
    src_s = str(src_resolved)

    # Our tree must be searched first (ahead of site-packages / other editable installs).
    sys.path[:] = [p for p in sys.path if Path(p).resolve() != src_resolved]
    sys.path.insert(0, src_s)

    for name in list(sys.modules):
        if name == "bg3_patcher" or name.startswith("bg3_patcher."):
            del sys.modules[name]

    import bg3_patcher  # noqa: PLC0415 - after path + purge

    loaded_root = Path(bg3_patcher.__file__).resolve().parent
    expected_root = pkg.resolve()
    if loaded_root != expected_root:
        print("[bg3-armor-patcher] Wrong code folder loaded:", file=sys.stderr)
        print(f"  got:      {loaded_root}", file=sys.stderr)
        print(f"  expected: {expected_root}", file=sys.stderr)
        print("[bg3-armor-patcher] Try: pip uninstall bg3-armor-patcher", file=sys.stderr)
        print("[bg3-armor-patcher] Then run: python run_ui.py", file=sys.stderr)
        return 2

    print(f"[bg3-armor-patcher] Using: {expected_root}", file=sys.stderr)

    from bg3_patcher.ui.app import main as ui_main  # noqa: PLC0415

    return ui_main()


if __name__ == "__main__":
    raise SystemExit(main())
