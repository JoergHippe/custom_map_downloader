#!/usr/bin/env python3
"""Install the plugin source tree into a local QGIS profile for development."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_NAME = "custom_map_downloader"
REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE = REPO_ROOT / PLUGIN_NAME


def windows_profile_root() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if not appdata:
        raise RuntimeError("APPDATA is not set; cannot resolve Windows QGIS profile path.")
    return Path(appdata) / "QGIS" / "QGIS3" / "profiles"


def linux_profile_root() -> Path:
    return Path.home() / ".local" / "share" / "QGIS" / "QGIS3" / "profiles"


def macos_profile_root() -> Path:
    return Path.home() / "Library" / "Application Support" / "QGIS" / "QGIS3" / "profiles"


def detect_profile_root() -> Path:
    if sys.platform.startswith("win"):
        return windows_profile_root()
    if sys.platform == "darwin":
        return macos_profile_root()
    return linux_profile_root()


def target_plugin_dir(profile: str) -> Path:
    return detect_profile_root() / profile / "python" / "plugins" / PLUGIN_NAME


def remove_existing(target: Path) -> None:
    if not target.exists() and not target.is_symlink():
        return
    if target.is_symlink():
        target.unlink()
        return
    if target.is_dir():
        shutil.rmtree(target)
        return
    target.unlink()


def install_copy(target: Path) -> None:
    shutil.copytree(PLUGIN_SOURCE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def install_link(target: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(target), str(PLUGIN_SOURCE)],
            check=True,
            capture_output=True,
            text=True,
        )
        return
    target.symlink_to(PLUGIN_SOURCE, target_is_directory=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="default", help="QGIS profile name")
    parser.add_argument(
        "--mode",
        choices=("link", "copy"),
        default="link",
        help="Install by directory link/junction or by full copy",
    )
    parser.add_argument(
        "--print-target",
        action="store_true",
        help="Only print the resolved target directory and exit",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove an existing deployed plugin from the target profile",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = target_plugin_dir(args.profile)

    if args.print_target:
        print(target)
        return 0

    if not PLUGIN_SOURCE.exists():
        raise RuntimeError(f"Plugin source directory not found: {PLUGIN_SOURCE}")

    target.parent.mkdir(parents=True, exist_ok=True)

    if args.remove:
        remove_existing(target)
        print(f"Removed {PLUGIN_NAME} from {target}")
        return 0

    remove_existing(target)

    if args.mode == "copy":
        install_copy(target)
    else:
        install_link(target)

    print(f"Installed {PLUGIN_NAME} -> {target} ({args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
