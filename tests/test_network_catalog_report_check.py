import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path("scripts/check_network_catalog_report.py")


class NetworkCatalogReportCheckTests(unittest.TestCase):
    def _run(self, payload: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "scenario_catalog_report.json"
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), str(report_path)],
                text=True,
                capture_output=True,
                check=False,
            )

    def test_accepts_ok_rows_for_official_catalog(self):
        proc = self._run(
            {
                "group_name": "official_webmaps_catalog",
                "rows": [{"scenario": "a", "status": "ok", "exit_code": 0}],
            }
        )
        self.assertEqual(proc.returncode, 0)

    def test_rejects_untracked_rows_for_official_catalog(self):
        proc = self._run(
            {
                "group_name": "official_webmaps_catalog",
                "rows": [{"scenario": "a", "status": "untracked", "exit_code": 0}],
            }
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("untracked", proc.stderr)

    def test_accepts_untracked_rows_for_non_strict_group(self):
        proc = self._run(
            {
                "group_name": "manual_probe_group",
                "rows": [{"scenario": "a", "status": "untracked", "exit_code": 0}],
            }
        )
        self.assertEqual(proc.returncode, 0)

    def test_rejects_error_rows(self):
        proc = self._run(
            {
                "group_name": "official_webmaps_catalog",
                "rows": [{"scenario": "a", "status": "error", "exit_code": 1}],
            }
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("error", proc.stderr)


if __name__ == "__main__":
    unittest.main()
