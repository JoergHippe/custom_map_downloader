#!/usr/bin/env python3
"""Validate a generated network-scenario report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path", help="Path to scenario_catalog_report.json")
    parser.add_argument(
        "--group",
        default="",
        help="Override group name instead of using the value embedded in the report",
    )
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        print(f"ERROR: report not found: {report_path}", file=sys.stderr)
        return 1

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    group_name = str(args.group or payload.get("group_name", "") or "official_webmaps_catalog")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        print("ERROR: invalid report format: rows must be a list", file=sys.stderr)
        return 1

    allowed_statuses = {"ok"} if group_name == "official_webmaps_catalog" else {"ok", "untracked"}
    bad_rows = [row for row in rows if str(row.get("status", "")) not in allowed_statuses]
    if bad_rows:
        for row in bad_rows:
            print(
                f"ERROR: {row.get('status')} scenario={row.get('scenario')} "
                f"exit={row.get('exit_code')}",
                file=sys.stderr,
            )
        return 1

    print(f"Network scenario report OK: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
