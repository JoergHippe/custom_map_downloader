"""Regression tests for report gates that run without the QGIS runtime."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATES = (
    ("scripts/check_scale_matrix_report.py", "scale_matrix", "case"),
    ("scripts/check_network_catalog_report.py", "official_webmaps_catalog", "scenario"),
)


class ReportGateTests(unittest.TestCase):
    """Both release gates must reject missing, empty and malformed results."""

    def run_gate(self, script: str, payload: dict) -> subprocess.CompletedProcess[str]:
        # A temporary JSON file keeps the test independent of real web services.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(ROOT / script), str(path)],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_empty_results_fail(self) -> None:
        for script, key, _ in GATES:
            with self.subTest(script=script):
                result = self.run_gate(script, {"matrix_key": key, "group_name": key, "rows": []})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("no test results", result.stderr)

    def test_non_object_rows_fail(self) -> None:
        for script, key, _ in GATES:
            with self.subTest(script=script):
                result = self.run_gate(
                    script, {"matrix_key": key, "group_name": key, "rows": ["bad row"]}
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("each row must be an object", result.stderr)

    def test_valid_results_pass(self) -> None:
        for script, key, name_field in GATES:
            with self.subTest(script=script):
                row = {name_field: "sample", "status": "ok", "exit_code": 0}
                result = self.run_gate(
                    script, {"matrix_key": key, "group_name": key, "rows": [row]}
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_success_status_with_failed_process_fails(self) -> None:
        for script, key, name_field in GATES:
            with self.subTest(script=script):
                row = {name_field: "sample", "status": "ok", "exit_code": 1}
                result = self.run_gate(
                    script, {"matrix_key": key, "group_name": key, "rows": [row]}
                )
                self.assertNotEqual(result.returncode, 0)

    def test_failed_results_fail(self) -> None:
        for script, key, name_field in GATES:
            with self.subTest(script=script):
                row = {name_field: "sample", "status": "error", "exit_code": 1}
                result = self.run_gate(
                    script, {"matrix_key": key, "group_name": key, "rows": [row]}
                )
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
