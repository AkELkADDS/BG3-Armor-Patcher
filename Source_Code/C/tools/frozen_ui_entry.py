"""PyInstaller entry for the BG3 Armor Patcher GUI (one-file build).

Author: AkELkA.
"""
from __future__ import annotations

import sys


def main() -> int:
    from bg3_patcher.ui.app import main as ui_main

    return ui_main()


if __name__ == "__main__":
    raise SystemExit(main())
