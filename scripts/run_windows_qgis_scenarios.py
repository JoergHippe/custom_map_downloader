#!/usr/bin/env python3
"""Run selected Windows QGIS network scenarios in isolated child processes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "tests" / "integration" / "config.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "network_scenarios"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def read_scenario_names(
    config: dict, group_name: str | None, explicit_names: list[str]
) -> list[str]:
    if explicit_names:
        return explicit_names
    if group_name:
        groups = config.get("scenario_groups", {}) or {}
        return [str(name) for name in groups.get(group_name, [])]
    return [str(s["name"]) for s in config.get("scenarios", []) if "name" in s]


def detect_python_qgis_bat() -> str:
    candidates = [
        r"C:\OSGeo4W64\bin\python-qgis.bat",
        r"C:\OSGeo4W\bin\python-qgis.bat",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("python-qgis.bat not found under OSGeo4W.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--group",
        help="Scenario group from tests/integration/config.json",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Explicit scenario name; may be passed multiple times",
    )
    args = parser.parse_args()

    config = load_config()
    report_dir = Path(os.environ.get("CMD_INTEGRATION_REPORT_DIR", str(DEFAULT_REPORT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)
    scenario_names = read_scenario_names(config, args.group, args.scenario)
    python_qgis = detect_python_qgis_bat()
    summary: list[dict[str, object]] = []

    if not scenario_names:
        (report_dir / "scenario_summary.json").write_text("[]\n", encoding="utf-8")
        print("No scenarios selected.")
        return 0

    for scenario_name in scenario_names:
        scenario_dir = report_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ALLOW_INTEGRATION_NETWORK"] = "1"
        env["SCENARIOS"] = scenario_name
        env["CMD_INTEGRATION_REPORT_DIR"] = str(scenario_dir)
        cmd = [
            python_qgis,
            "-m",
            "unittest",
            "-v",
            "tests.integration.test_export_network",
        ]
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )
        (scenario_dir / "stdout.log").write_text(proc.stdout, encoding="utf-8", errors="replace")
        (scenario_dir / "stderr.log").write_text(proc.stderr, encoding="utf-8", errors="replace")
        summary.append(
            {
                "scenario": scenario_name,
                "exit_code": proc.returncode,
                "report_dir": str(scenario_dir),
            }
        )

    (report_dir / "scenario_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    failures = [entry for entry in summary if int(entry["exit_code"]) != 0]
    if failures:
        for failure in failures:
            print(
                f"FAILED: {failure['scenario']} (exit_code={failure['exit_code']})",
                file=sys.stderr,
            )
        return 1

    print(f"Scenario catalog OK: {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
