#!/usr/bin/env python3
"""Build the X Cleaner Chrome extension.

Copies src/extension/ → output/x-cleaner/ and zips into output/x-cleaner.zip.

Usage:
    python src/build.py
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent           # src/
PROJECT_ROOT = HERE.parent                       # project root
SRC = HERE / "extension"
OUT_DIR = PROJECT_ROOT / "output" / "x-cleaner"
OUT_ZIP = PROJECT_ROOT / "output" / "x-cleaner.zip"


def copy_tree(src: Path, dst: Path) -> int:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return sum(1 for _ in dst.rglob("*") if _.is_file())


def zip_dir(src: Path, zip_path: Path) -> int:
    if zip_path.exists():
        zip_path.unlink()
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for f in files:
                p = Path(root) / f
                z.write(p, p.relative_to(src))
                count += 1
    return count


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source assets missing: {SRC}", file=sys.stderr)
        return 1
    OUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    n_files = copy_tree(SRC, OUT_DIR)
    n_zip = zip_dir(OUT_DIR, OUT_ZIP)
    size_kb = OUT_ZIP.stat().st_size / 1024
    print(f"unpacked dir : {OUT_DIR.relative_to(PROJECT_ROOT)}  ({n_files} files)")
    print(f"zip          : {OUT_ZIP.relative_to(PROJECT_ROOT)}  ({n_zip} files, {size_kb:.1f} KB)")
    print()
    print("Install (Chrome / Edge / Brave):")
    print("  1. Open chrome://extensions")
    print("  2. Toggle Developer mode (top right)")
    print("  3. Load unpacked → pick output/x-cleaner/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
