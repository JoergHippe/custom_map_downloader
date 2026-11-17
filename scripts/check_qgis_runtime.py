#!/usr/bin/env python3
"""Fail-closed smoke probe using real QGIS/Qt bindings (never test stubs)."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Running a file from scripts/ otherwise hides the repository root from sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--major", type=int, required=True, choices=(3, 4))
    args = parser.parse_args()

    from qgis.core import Qgis, QgsApplication
    from qgis.PyQt.QtCore import QT_VERSION_STR

    qgis_major = int(str(Qgis.QGIS_VERSION).split(".", 1)[0])
    qt_major = int(QT_VERSION_STR.split(".", 1)[0])
    expected = (args.major, 5 if args.major == 3 else 6)
    if (qgis_major, qt_major) != expected:
        raise RuntimeError(
            f"Expected QGIS/Qt {expected}, found {Qgis.QGIS_VERSION}/{QT_VERSION_STR}"
        )

    # Import the GUI and exporter through actual QGIS bindings before testing.
    app = QgsApplication([], True)
    app.initQgis()
    try:
        for module in (
            "custom_map_downloader.core.exporter",
            "custom_map_downloader.CustomMapDownloader_dialog",
            "custom_map_downloader.CustomMapDownloader",
        ):
            importlib.import_module(module)

        from custom_map_downloader import classFactory

        plugin = classFactory(object())
        if plugin is None:
            raise RuntimeError("classFactory returned None")
        print(f"PASS: QGIS {Qgis.QGIS_VERSION}, Qt {QT_VERSION_STR}, plugin classFactory")
    finally:
        if "plugin" in locals():
            del plugin
        app.exitQgis()
    return 0


if __name__ == "__main__":
    sys.exit(main())
