#!/usr/bin/env python3
"""Summarize isolated Windows/QGIS network-scenario artifacts."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "test" / "integration" / "config.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts"


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def expected_hashes_by_scenario(group_name: str) -> dict[str, str]:
    config = load_config()
    scenarios = {str(item["name"]): item for item in config.get("scenarios", []) if "name" in item}
    names = [str(name) for name in (config.get("scenario_groups", {}) or {}).get(group_name, [])]
    return {
        name: str((scenarios.get(name, {}) or {}).get("expected_sha256", "") or "")
        for name in names
    }


def resolve_scenario_report_dir(report_dir: Path, entry: dict[str, Any]) -> Path:
    raw = str(entry.get("report_dir", "") or "")
    candidate = Path(raw) if raw else report_dir / str(entry["scenario"])
    if candidate.exists():
        return candidate
    return report_dir / str(entry["scenario"])


def collect_scenario_results(report_dir: Path) -> dict[str, dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    summary_path = report_dir / "scenario_summary.json"
    if not summary_path.exists():
        return scenarios

    for entry in load_json(summary_path):
        scenario_name = str(entry["scenario"])
        scenario_dir = resolve_scenario_report_dir(report_dir, entry)
        scenario_result: dict[str, Any] = {
            "scenario": scenario_name,
            "exit_code": int(entry["exit_code"]),
            "report_dir": str(scenario_dir),
            "result": {},
        }
        scenario_json = scenario_dir / "network_scenarios.json"
        if scenario_json.exists():
            payload = load_json(scenario_json)
            if payload:
                scenario_result["result"] = payload[0]
        scenarios[scenario_name] = scenario_result
    return scenarios


def compare_against_expected(
    scenarios: dict[str, dict[str, Any]],
    expected_hashes: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_name, expected_hash in expected_hashes.items():
        item = scenarios.get(scenario_name, {})
        result = item.get("result", {}) if isinstance(item, dict) else {}
        exit_code = int(item.get("exit_code", 1) if isinstance(item, dict) else 1)
        actual_hash = str(result.get("sha256", "") or "")
        if exit_code != 0:
            status = "error"
        elif not result:
            status = "missing"
        elif expected_hash and expected_hash != actual_hash:
            status = "drift"
        elif expected_hash:
            status = "ok"
        else:
            status = "untracked"

        rows.append(
            {
                "scenario": scenario_name,
                "exit_code": exit_code,
                "status": status,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "width_px": result.get("width_px", ""),
                "height_px": result.get("height_px", ""),
            }
        )
    return rows


def render_markdown(group_name: str, rows: list[dict[str, Any]]) -> str:
    header = [
        f"## Network Scenario Report: `{group_name}`",
        "",
        "| Scenario | Status | Exit | Size | Hash |",
        "| --- | --- | ---: | --- | --- |",
    ]
    body = []
    for row in rows:
        size = f"{row['width_px']}x{row['height_px']}" if row["width_px"] != "" else "-"
        hash_text = row["actual_hash"][:12] if row["actual_hash"] else "-"
        body.append(
            f"| `{row['scenario']}` | `{row['status']}` | {row['exit_code']} | "
            f"`{size}` | `{hash_text}` |"
        )
    return "\n".join(header + body + [""])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group",
        default=os.environ.get("CMD_SCENARIO_GROUP", "official_webmaps_catalog"),
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
    scenarios = collect_scenario_results(report_dir)
    expected = expected_hashes_by_scenario(args.group)
    rows = compare_against_expected(scenarios, expected)
    payload = {"group_name": args.group, "rows": rows}

    json_path = report_dir / "scenario_catalog_report.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    markdown = render_markdown(args.group, rows)
    md_path = report_dir / "scenario_catalog_report.md"
    md_path.write_text(markdown, encoding="utf-8")

    if args.write_summary:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
        if summary_path:
            with open(summary_path, "a", encoding="utf-8") as fh:
                fh.write(markdown)

    bad_rows = [row for row in rows if row["status"] in {"drift", "missing", "error"}]
    if bad_rows:
        for row in bad_rows:
            print(f"{row['status'].upper()}: {row['scenario']} " f"(exit={row['exit_code']})")
        return 1

    print(f"Network scenario report written to {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
