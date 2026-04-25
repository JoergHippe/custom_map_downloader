#!/usr/bin/env python3
"""Run Windows QGIS integration cases in isolated child processes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "tests" / "integration" / "config.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "integration"


def read_scale_case_names(matrix_key: str) -> list[str]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return [str(case["name"]) for case in config.get(matrix_key, []) if "name" in case]


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
        "--matrix-key",
        default=os.environ.get("CMD_SCALE_MATRIX_KEY", "scale_matrix"),
        help="JSON key in tests/integration/config.json to execute",
    )
    args = parser.parse_args()

    report_dir = Path(os.environ.get("CMD_INTEGRATION_REPORT_DIR", str(DEFAULT_REPORT_DIR)))
    report_dir.mkdir(parents=True, exist_ok=True)

    python_qgis = detect_python_qgis_bat()
    case_names = read_scale_case_names(args.matrix_key)
    summary: list[dict[str, object]] = []

    if not case_names:
        (report_dir / "scale_matrix_summary.json").write_text("[]\n", encoding="utf-8")
        print(f"No cases configured for matrix '{args.matrix_key}'.")
        return 0

    for case_name in case_names:
        case_report_dir = report_dir / case_name
        case_report_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["ALLOW_INTEGRATION_NETWORK"] = "1"
        env["SCENARIOS"] = case_name
        env["CMD_INTEGRATION_REPORT_DIR"] = str(case_report_dir)
        env["CMD_SCALE_MATRIX_KEY"] = args.matrix_key

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
        (case_report_dir / "stdout.log").write_text(proc.stdout, encoding="utf-8", errors="replace")
        (case_report_dir / "stderr.log").write_text(proc.stderr, encoding="utf-8", errors="replace")
        summary.append(
            {
                "case": case_name,
                "exit_code": proc.returncode,
                "report_dir": str(case_report_dir),
            }
        )

    (report_dir / "scale_matrix_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    failures = [entry for entry in summary if int(entry["exit_code"]) != 0]
    if failures:
        for failure in failures:
            print(
                f"FAILED: {failure['case']} (exit_code={failure['exit_code']})",
                file=sys.stderr,
            )
        return 1

    print(f"Scale matrix OK: {report_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
