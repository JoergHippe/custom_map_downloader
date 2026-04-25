import json
import tempfile
import unittest
from pathlib import Path

from scripts import summarize_network_catalog


class NetworkCatalogSummaryTests(unittest.TestCase):
    def test_compare_against_expected_marks_ok_drift_and_missing(self):
        scenarios = {
            "ok_case": {
                "scenario": "ok_case",
                "exit_code": 0,
                "report_dir": "x",
                "result": {"sha256": "aaa", "width_px": 10, "height_px": 10},
            },
            "missing_case": {
                "scenario": "missing_case",
                "exit_code": 0,
                "report_dir": "y",
                "result": {},
            },
        }
        expected = {"ok_case": "aaa", "drift_case": "bbb", "missing_case": "zzz"}

        rows = summarize_network_catalog.compare_against_expected(scenarios, expected)
        status_by_name = {row["scenario"]: row["status"] for row in rows}

        self.assertEqual(status_by_name["ok_case"], "ok")
        self.assertEqual(status_by_name["drift_case"], "error")
        self.assertEqual(status_by_name["missing_case"], "missing")

    def test_collect_scenario_results_reads_network_scenarios_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scenario_dir = root / "scenario_a"
            scenario_dir.mkdir()
            (root / "scenario_summary.json").write_text(
                json.dumps(
                    [{"scenario": "scenario_a", "exit_code": 0, "report_dir": str(scenario_dir)}]
                ),
                encoding="utf-8",
            )
            (scenario_dir / "network_scenarios.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "scenario_a",
                            "sha256": "abc",
                            "width_px": 10,
                            "height_px": 20,
                            "result": "ok",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            scenarios = summarize_network_catalog.collect_scenario_results(root)

        self.assertEqual(scenarios["scenario_a"]["result"]["sha256"], "abc")
        self.assertEqual(scenarios["scenario_a"]["result"]["width_px"], 10)

    def test_collect_scenario_results_falls_back_from_windows_report_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scenario_dir = root / "scenario_b"
            scenario_dir.mkdir()
            (root / "scenario_summary.json").write_text(
                json.dumps(
                    [
                        {
                            "scenario": "scenario_b",
                            "exit_code": 0,
                            "report_dir": r"D:\temp\scenario_b",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (scenario_dir / "network_scenarios.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "scenario_b",
                            "sha256": "def",
                            "width_px": 7,
                            "height_px": 8,
                            "result": "ok",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            scenarios = summarize_network_catalog.collect_scenario_results(root)

        self.assertEqual(scenarios["scenario_b"]["result"]["sha256"], "def")


if __name__ == "__main__":
    unittest.main()
