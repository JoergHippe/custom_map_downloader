#!/usr/bin/env python3
"""Run one Windows/QGIS scale case per label in isolated child processes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.run_windows_qgis_matrix import CONFIG_PATH, REPO_ROOT, detect_python_qgis_bat

DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "scale_probe"


def load_case_names(matrix_key: str) -> dict[str, dict[str, object]]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {
        str(case["name"]): case
        for case in config.get(matrix_key, [])
        if isinstance(case, dict) and "name" in case
    }


def run_probe(
    *,
    python_qgis: str,
    case_name: str,
    matrix_key: str,
    label: str,
    report_dir: Path,
) -> int:
    label_report_dir = report_dir / label
    label_report_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ALLOW_INTEGRATION_NETWORK"] = "1"
    env["SCENARIOS"] = case_name
    env["CMD_INTEGRATION_REPORT_DIR"] = str(label_report_dir)
    env["CMD_SCALE_MATRIX_KEY"] = matrix_key
    env["CMD_SCALE_ONLY"] = label

    cmd = [
        python_qgis,
        "-m",
        "unittest",
        "-v",
        "test.integration.test_export_network",
    ]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    (label_report_dir / "stdout.log").write_text(proc.stdout, encoding="utf-8", errors="replace")
    (label_report_dir / "stderr.log").write_text(proc.stderr, encoding="utf-8", errors="replace")
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_name", help="Scale case name from integration config")
    parser.add_argument(
        "--matrix-key",
        default=os.environ.get("CMD_SCALE_MATRIX_KEY", "experimental_scale_matrix"),
        help="JSON key in test/integration/config.json to probe",
    )
    parser.add_argument(
        "--label",
        choices=["small", "large", "both"],
        default="both",
        help="Which scale label to run",
    )
    args = parser.parse_args()

    cases = load_case_names(args.matrix_key)
    if args.case_name not in cases:
        print(
            f"Case '{args.case_name}' not found under matrix '{args.matrix_key}'.",
            file=sys.stderr,
        )
        return 2

    report_root = Path(
        os.environ.get(
            "CMD_INTEGRATION_REPORT_DIR",
            str(DEFAULT_REPORT_DIR / args.case_name),
        )
    )
    report_root.mkdir(parents=True, exist_ok=True)
    python_qgis = detect_python_qgis_bat()

    labels = ["small", "large"] if args.label == "both" else [args.label]
    summary: list[dict[str, object]] = []
    failed = False
    for label in labels:
        exit_code = run_probe(
            python_qgis=python_qgis,
            case_name=args.case_name,
            matrix_key=args.matrix_key,
            label=label,
            report_dir=report_root,
        )
        summary.append(
            {
                "case": args.case_name,
                "matrix_key": args.matrix_key,
                "label": label,
                "exit_code": exit_code,
                "report_dir": str(report_root / label),
            }
        )
        if exit_code != 0:
            failed = True

    (report_root / "probe_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    if failed:
        for entry in summary:
            if int(entry["exit_code"]) != 0:
                print(
                    f"FAILED: {entry['case']} [{entry['label']}]"
                    f" (exit_code={entry['exit_code']})",
                    file=sys.stderr,
                )
        return 1

    print(f"Scale probe OK: {report_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
