#!/usr/bin/env python3
"""Run the standard local preflight checks for plugin development."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_PATH = REPO_ROOT / "custom_map_downloader" / "metadata.txt"


def read_version() -> str:
    for line in METADATA_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("version="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"version= not found in {METADATA_PATH}")


def resolve_qgis_plugin_ci() -> list[str]:
    sibling = Path(sys.executable).with_name("qgis-plugin-ci")
    if sibling.exists():
        return [str(sibling)]

    fallback = shutil.which("qgis-plugin-ci")
    if fallback:
        return [fallback]

    raise RuntimeError("qgis-plugin-ci not found next to the active Python or in PATH.")


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def main() -> int:
    run(
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "test.test_init",
            "test.test_validation",
            "test.test_exporter_validation",
            "test.test_profile_io",
            "test.test_progress_keys",
        ]
    )

    version = read_version()
    run(resolve_qgis_plugin_ci() + ["package", version, "-c"])
    run([sys.executable, "scripts/check_package.py"])
    print("Dev check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
