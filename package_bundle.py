#!/usr/bin/env python3
"""
Package the Pinball Cabinet apps into a single distributable zip.

Designed to run in GitHub Actions AFTER PyInstaller has produced the two
executables in dist/. It bundles everything an end user needs into

    dist/pinball-cabinet-bundle.zip

containing:

    pinball_frontend.exe
    table_manager.exe
    README.md
    config.json      (template)
    tables.json      (template)

The zip is written into dist/ so the actions/upload-artifact step picks it up.

Usage (locally or in CI):
    python package_bundle.py

Exits non-zero if any required file is missing, so a broken build fails loudly
instead of shipping an incomplete bundle.

Pure standard library - no dependencies. Python 3.10+.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

# This script lives in the repo root, so its folder IS the repo root.
REPO_ROOT = Path(__file__).resolve().parent
DIST_DIR = REPO_ROOT / "dist"
BUNDLE_NAME = "pinball-cabinet-bundle.zip"

# (source path on disk, name inside the zip)
CONTENTS: list[tuple[Path, str]] = [
    (DIST_DIR / "pinball_frontend.exe", "pinball_frontend.exe"),
    (DIST_DIR / "table_manager.exe", "table_manager.exe"),
    (REPO_ROOT / "README.md", "README.md"),
    (REPO_ROOT / "config.json", "config.json"),
    (REPO_ROOT / "tables.json", "tables.json"),
]


def main() -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    bundle_path = DIST_DIR / BUNDLE_NAME

    # Remove any stale bundle so we never accidentally nest it inside itself.
    if bundle_path.exists():
        bundle_path.unlink()

    missing = [str(src) for src, _ in CONTENTS if not src.is_file()]
    if missing:
        print("ERROR: required files are missing, cannot build bundle:")
        for m in missing:
            print(f"  - {m}")
        return 1

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in CONTENTS:
            zf.write(src, arcname)
            print(f"added {arcname:<24} ({src.stat().st_size:,} bytes)")

    print(f"\nCreated {bundle_path} ({bundle_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
