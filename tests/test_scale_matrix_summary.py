import json
import tempfile
import unittest
from pathlib import Path

from scripts import summarize_scale_matrix


class ScaleMatrixSummaryTests(unittest.TestCase):
    def test_compare_against_expected_marks_ok_drift_and_missing(self):
        cases = {
            "case_ok": {
                "case": "case_ok",
                "exit_code": 0,
                "report_dir": "x",
                "labels": {
                    "small": {"sha256": "aaa", "width_px": 10, "height_px": 10, "scale": 1000.0},
                    "large": {"sha256": "bbb", "width_px": 5, "height_px": 5, "scale": 2000.0},
                },
            },
            "case_missing": {
                "case": "case_missing",
                "exit_code": 0,
                "report_dir": "y",
                "labels": {},
            },
        }
        expected = {
            "case_ok": {"small": "aaa", "large": "ccc"},
            "case_missing": {"small": "zzz"},
        }

        rows = summarize_scale_matrix.compare_against_expected(cases, expected)
        status_by_key = {(row["case"], row["label"]): row["status"] for row in rows}

        self.assertEqual(status_by_key[("case_ok", "small")], "ok")
        self.assertEqual(status_by_key[("case_ok", "large")], "drift")
        self.assertEqual(status_by_key[("case_missing", "-")], "missing")

    def test_collect_case_results_reads_scale_matrix_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_dir = root / "case_a"
            case_dir.mkdir()
            (root / "scale_matrix_summary.json").write_text(
                json.dumps([{"case": "case_a", "exit_code": 0, "report_dir": str(case_dir)}]),
                encoding="utf-8",
            )
            (case_dir / "scale_matrix.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "case_a",
                            "results": [
                                {
                                    "label": "small",
                                    "sha256": "abc",
                                    "width_px": 10,
                                    "height_px": 20,
                                    "scale": 1000.0,
                                }
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            cases = summarize_scale_matrix.collect_case_results(root)

        self.assertEqual(cases["case_a"]["labels"]["small"]["sha256"], "abc")
        self.assertEqual(cases["case_a"]["labels"]["small"]["width_px"], 10)

    def test_collect_case_results_falls_back_from_windows_report_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            case_dir = root / "case_b"
            case_dir.mkdir()
            (root / "scale_matrix_summary.json").write_text(
                json.dumps(
                    [
                        {
                            "case": "case_b",
                            "exit_code": 0,
                            "report_dir": r"D:\temp\case_b",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (case_dir / "scale_matrix.json").write_text(
                json.dumps(
                    [
                        {
                            "name": "case_b",
                            "results": [
                                {
                                    "label": "large",
                                    "sha256": "def",
                                    "width_px": 7,
                                    "height_px": 8,
                                    "scale": 2000.0,
                                }
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            cases = summarize_scale_matrix.collect_case_results(root)

        self.assertEqual(cases["case_b"]["labels"]["large"]["sha256"], "def")


if __name__ == "__main__":
    unittest.main()
