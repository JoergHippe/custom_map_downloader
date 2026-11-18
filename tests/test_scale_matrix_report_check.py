import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path("scripts/check_scale_matrix_report.py")


class ScaleMatrixReportCheckTests(unittest.TestCase):
    def _run(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "scale_matrix_report.json"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(report_path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_accepts_ok_rows_for_required_matrix(self):
        proc = self._run(
            {
                "matrix_key": "scale_matrix",
                "rows": [
                    {"case": "a", "label": "small", "status": "ok", "exit_code": 0},
                ],
            }
        )
        self.assertEqual(proc.returncode, 0)

    def test_accepts_untracked_rows_for_required_matrix(self):
        proc = self._run(
            {
                "matrix_key": "scale_matrix",
                "rows": [
                    {"case": "b", "label": "large", "status": "untracked", "exit_code": 0},
                ],
            }
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("NOTICE", proc.stdout)

    def test_accepts_untracked_rows_for_experimental_matrix(self):
        proc = self._run(
            {
                "matrix_key": "experimental_scale_matrix",
                "rows": [
                    {"case": "b", "label": "large", "status": "untracked", "exit_code": 0},
                ],
            }
        )
        self.assertEqual(proc.returncode, 0)

    def test_accepts_drift_rows_but_rejects_nonzero_exit(self):
        proc = self._run(
            {
                "matrix_key": "scale_matrix",
                "rows": [
                    {"case": "a", "label": "small", "status": "drift", "exit_code": 0},
                ],
            }
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("NOTICE", proc.stdout)
        payload = {
            "matrix_key": "scale_matrix",
            "rows": [{"case": "a", "label": "small", "status": "drift", "exit_code": 3}],
        }
        self.assertNotEqual(self._run(payload).returncode, 0)

    def test_rejects_empty_matrix(self):
        self.assertNotEqual(self._run({"matrix_key": "scale_matrix", "rows": []}).returncode, 0)


    def test_rejects_malformed_rows(self):
        # A malformed row must fail closed instead of raising an unhandled exception.
        payload = {"matrix_key": "scale_matrix", "rows": ["invalid"]}
        self.assertNotEqual(self._run(payload).returncode, 0)

    def test_rejects_success_status_with_failed_child_process(self):
        # A success label cannot overrule a failed QGIS child process.
        payload = {
            "matrix_key": "scale_matrix",
            "rows": [{"case": "sample", "status": "ok", "exit_code": 1}],
        }
        self.assertNotEqual(self._run(payload).returncode, 0)

if __name__ == "__main__":
    unittest.main()
