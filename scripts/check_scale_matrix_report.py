#!/usr/bin/env python3
"""Validate a generated scale-matrix report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path", help="Path to scale_matrix_report.json")
    parser.add_argument(
        "--matrix-key",
        default="",
        help="Override matrix key instead of using the value embedded in the report",
    )
    args = parser.parse_args()

    report_path = Path(args.report_path)
    if not report_path.exists():
        print(f"ERROR: report not found: {report_path}", file=sys.stderr)
        return 1

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    matrix_key = str(args.matrix_key or payload.get("matrix_key", "") or "scale_matrix")
    rows = payload.get("rows", [])
    if not isinstance(rows, list):
        print("ERROR: invalid report format: rows must be a list", file=sys.stderr)
        return 1

    allowed_statuses = {"ok"} if matrix_key == "scale_matrix" else {"ok", "untracked"}
    bad_rows = [row for row in rows if str(row.get("status", "")) not in allowed_statuses]
    if bad_rows:
        for row in bad_rows:
            print(
                f"ERROR: {row.get('status')} case={row.get('case')} "
                f"label={row.get('label')} exit={row.get('exit_code')}",
                file=sys.stderr,
            )
        return 1

    print(f"Scale matrix report OK: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
