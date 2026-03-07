#!/usr/bin/env python3
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

I18N_DIR = Path("custom_map_downloader/i18n")


def summarize(ts_path: Path) -> tuple[int, int]:
    root = ET.parse(ts_path).getroot()
    total = 0
    unfinished = 0
    for msg in root.findall(".//message"):
        total += 1
        translation = msg.find("translation")
        if translation is None:
            unfinished += 1
            continue
        if translation.get("type") == "unfinished":
            unfinished += 1
    return total, unfinished


def main() -> int:
    if not I18N_DIR.exists():
        print("No i18n directory found.", file=sys.stderr)
        return 1

    ts_files = sorted(I18N_DIR.glob("*.ts"))
    if not ts_files:
        print("No .ts files found.", file=sys.stderr)
        return 1

    for ts_file in ts_files:
        total, unfinished = summarize(ts_file)
        finished = total - unfinished
        percent = 100.0 if total == 0 else (finished / total) * 100.0
        print(f"{ts_file}: {finished}/{total} translated ({percent:.1f}%), {unfinished} unfinished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
