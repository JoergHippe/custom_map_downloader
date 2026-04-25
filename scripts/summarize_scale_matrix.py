#!/usr/bin/env python3
"""Summarize Windows/QGIS scale-matrix artifacts into JSON and Markdown."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "tests" / "integration" / "config.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def expected_hashes_by_case(matrix_key: str) -> dict[str, dict[str, str]]:
    config = load_config()
    out: dict[str, dict[str, str]] = {}
    for case in config.get(matrix_key, []):
        if not isinstance(case, dict) or "name" not in case:
            continue
        hashes = case.get("expected_hashes", {}) or {}
        out[str(case["name"])] = {
            str(label): str(digest)
            for label, digest in hashes.items()
            if str(label) in {"small", "large"} and str(digest)
        }
    return out


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_case_report_dir(report_dir: Path, entry: dict[str, Any]) -> Path:
    raw = str(entry.get("report_dir", "") or "")
    candidate = Path(raw) if raw else report_dir / str(entry["case"])
    if candidate.exists():
        return candidate
    return report_dir / str(entry["case"])


def collect_case_results(report_dir: Path) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    summary_path = report_dir / "scale_matrix_summary.json"
    if not summary_path.exists():
        return cases

    for entry in load_json(summary_path):
        case_name = str(entry["case"])
        case_dir = resolve_case_report_dir(report_dir, entry)
        case_result: dict[str, Any] = {
            "case": case_name,
            "exit_code": int(entry["exit_code"]),
            "report_dir": str(case_dir),
            "labels": {},
        }
        scale_json = case_dir / "scale_matrix.json"
        if scale_json.exists():
            payload = load_json(scale_json)
            if payload:
                for item in payload[0].get("results", []):
                    label = str(item["label"])
                    case_result["labels"][label] = {
                        "sha256": str(item["sha256"]),
                        "width_px": int(item["width_px"]),
                        "height_px": int(item["height_px"]),
                        "scale": float(item["scale"]),
                    }
        cases[case_name] = case_result
    return cases


def compare_against_expected(
    cases: dict[str, dict[str, Any]],
    expected: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_name, case in sorted(cases.items()):
        labels = case.get("labels", {})
        expected_case = expected.get(case_name, {})
        if not labels:
            rows.append(
                {
                    "case": case_name,
                    "label": "-",
                    "exit_code": int(case["exit_code"]),
                    "status": "error" if int(case["exit_code"]) != 0 else "missing",
                    "expected_hash": "",
                    "actual_hash": "",
                    "width_px": "",
                    "height_px": "",
                }
            )
            continue

        for label in ("small", "large"):
            result = labels.get(label)
            if result is None:
                rows.append(
                    {
                        "case": case_name,
                        "label": label,
                        "exit_code": int(case["exit_code"]),
                        "status": "missing",
                        "expected_hash": expected_case.get(label, ""),
                        "actual_hash": "",
                        "width_px": "",
                        "height_px": "",
                    }
                )
                continue

            expected_hash = expected_case.get(label, "")
            actual_hash = str(result["sha256"])
            if int(case["exit_code"]) != 0:
                status = "error"
            elif expected_hash and expected_hash != actual_hash:
                status = "drift"
            elif expected_hash:
                status = "ok"
            else:
                status = "untracked"

            rows.append(
                {
                    "case": case_name,
                    "label": label,
                    "exit_code": int(case["exit_code"]),
                    "status": status,
                    "expected_hash": expected_hash,
                    "actual_hash": actual_hash,
                    "width_px": int(result["width_px"]),
                    "height_px": int(result["height_px"]),
                }
            )
    return rows


def render_markdown(matrix_key: str, rows: list[dict[str, Any]]) -> str:
    header = [
        f"## Scale Matrix Report: `{matrix_key}`",
        "",
        "| Case | Label | Status | Exit | Size | Hash |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    body = []
    for row in rows:
        size = f"{row['width_px']}x{row['height_px']}" if row["width_px"] != "" else "-"
        hash_text = row["actual_hash"][:12] if row["actual_hash"] else "-"
        body.append(
            f"| `{row['case']}` | `{row['label']}` | `{row['status']}` | "
            f"{row['exit_code']} | `{size}` | `{hash_text}` |"
        )
    return "\n".join(header + body + [""])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--matrix-key",
        default=os.environ.get("CMD_SCALE_MATRIX_KEY", "scale_matrix"),
    )
    parser.add_argument(
        "--report-dir",
        default=os.environ.get("CMD_INTEGRATION_REPORT_DIR", str(DEFAULT_REPORT_DIR)),
    )
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Append Markdown summary to GITHUB_STEP_SUMMARY if available",
    )
    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    cases = collect_case_results(report_dir)
    expected = expected_hashes_by_case(args.matrix_key)
    rows = compare_against_expected(cases, expected)
    payload = {
        "matrix_key": args.matrix_key,
        "rows": rows,
    }
    json_path = report_dir / "scale_matrix_report.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    markdown = render_markdown(args.matrix_key, rows)
    md_path = report_dir / "scale_matrix_report.md"
    md_path.write_text(markdown, encoding="utf-8")

    if args.write_summary:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(markdown)

    drifts = [row for row in rows if row["status"] == "drift"]
    errors = [row for row in rows if row["status"] in {"error", "missing"}]
    if drifts or errors:
        for row in drifts + errors:
            print(
                f"{row['status'].upper()}: {row['case']} [{row['label']}] "
                f"(exit={row['exit_code']})"
            )
        return 1

    print(f"Scale matrix report written to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
