from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bg3_patcher.merger import run_patch
from bg3_patcher.models import PatchValidationError
from bg3_patcher.presets import load_preset

__author__ = "AkELkA"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate BG3 armor patch files from a preset.",
        epilog="Author: AkELkA.",
    )
    parser.add_argument("preset", type=Path, help="Path to a preset JSON file.")
    args = parser.parse_args(argv)

    try:
        config = load_preset(args.preset)
        report = run_patch(config)
    except PatchValidationError as exc:
        print("Validation failed:", file=sys.stderr)
        for message in exc.messages:
            print(f"- {message}", file=sys.stderr)
        return 2

    print("Patch complete.")
    print(f"Written files: {len(report.written_files)}")
    if report.warnings:
        print(f"Warnings: {len(report.warnings)}")
    if report.skipped:
        print(f"Skipped: {len(report.skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
