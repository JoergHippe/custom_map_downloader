#!/usr/bin/env python3
"""Validate the packaged QGIS plugin archive."""

import sys
import zipfile
from pathlib import Path

PLUGIN_DIR = Path("custom_map_downloader")
METADATA_PATH = PLUGIN_DIR / "metadata.txt"

REQUIRED_ENTRIES = {
    "custom_map_downloader/__init__.py",
    "custom_map_downloader/CustomMapDownloader.py",
    "custom_map_downloader/CustomMapDownloader_dialog.py",
    "custom_map_downloader/CustomMapDownloader_dialog_base.ui",
    "custom_map_downloader/metadata.txt",
    "custom_map_downloader/resources.py",
    "custom_map_downloader/resources_rc.py",
    "custom_map_downloader/i18n/CustomMapDownloader_de.qm",
}

FORBIDDEN_SUFFIXES = (
    ".ts",
    ".qrc",
)

FORBIDDEN_PARTS = (
    "/test/",
    "/tests/",
    "/.github/",
)

FORBIDDEN_ENTRIES = {
    "custom_map_downloader/CustomMapDownloader_dialog_base_ui.py",
}


def read_version() -> str:
    for line in METADATA_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"version= not found in {METADATA_PATH}")


def main() -> int:
    version = read_version()
    archive_path = Path(f"custom_map_downloader.{version}.zip")
    if not archive_path.exists():
        raise RuntimeError(f"Archive not found: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    missing = sorted(REQUIRED_ENTRIES - names)
    if missing:
        raise RuntimeError(f"Archive is missing required files: {missing}")

    forbidden = sorted(
        name
        for name in names
        if name in FORBIDDEN_ENTRIES
        or name.endswith(FORBIDDEN_SUFFIXES)
        or any(part in name for part in FORBIDDEN_PARTS)
    )
    if forbidden:
        raise RuntimeError(f"Archive contains forbidden files: {forbidden}")

    print(f"Archive OK: {archive_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
