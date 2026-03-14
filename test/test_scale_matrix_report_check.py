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

    def test_accepts_ok_and_untracked_rows(self):
        proc = self._run(
            {
                "matrix_key": "scale_matrix",
                "rows": [
                    {"case": "a", "label": "small", "status": "ok", "exit_code": 0},
                    {"case": "b", "label": "large", "status": "untracked", "exit_code": 0},
                ],
            }
        )
        self.assertEqual(proc.returncode, 0)

    def test_rejects_drift_rows(self):
        proc = self._run(
            {
                "matrix_key": "scale_matrix",
                "rows": [
                    {"case": "a", "label": "small", "status": "drift", "exit_code": 0},
                ],
            }
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("drift", proc.stderr)


if __name__ == "__main__":
    unittest.main()
