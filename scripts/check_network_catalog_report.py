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

    # A source data update must not fail a valid raster export.
    # Missing/failed scenarios and nonzero child exit codes still fail closed.
    if not rows:
        print("ERROR: network scenario report has no rows", file=sys.stderr)
        return 1
    allowed_statuses = {"ok", "drift", "untracked"}
    bad_rows = [
        row
        for row in rows
        if not isinstance(row, dict)
        or row.get("status") not in allowed_statuses
        or row.get("exit_code") != 0
    ]
    if bad_rows:
        for row in bad_rows:
            print(f"ERROR: invalid or failed scenario report row: {row!r}", file=sys.stderr)
        return 1

    notices = [row for row in rows if row["status"] in {"drift", "untracked"}]
    for row in notices:
        print(f"NOTICE: historical hash {row['status']} for {row.get('scenario')}")
    print(f"Network scenario report OK: {group_name}: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
