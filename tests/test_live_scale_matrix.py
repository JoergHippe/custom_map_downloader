"""Offline validation of official live scale-matrix runner constraints."""

import unittest

from scripts.run_live_scale_matrix import check_case_report, validate_matrix


class LiveScaleMatrixTests(unittest.TestCase):
    def test_preflight_rejects_oversized_or_empty_matrix(self):
        case = {
            "name": "case", "extent": {"west": 0, "east": 100, "south": 0, "north": 100},
            "small_scale": 1000, "large_scale": 5000,
        }
        config = {"scale_matrix": [case]}
        results = validate_matrix(config, "scale_matrix", 2_000_000)
        self.assertEqual(len(results), 1)
        self.assertNotEqual(results[0]["dimensions"]["small"], results[0]["dimensions"]["large"])
        with self.assertRaises(ValueError):
            validate_matrix(config, "scale_matrix", 100)
        with self.assertRaises(ValueError):
            validate_matrix(config, "missing", 2_000_000)

    def test_each_scale_and_dimensions_are_required(self):
        case = {"name": "case", "dimensions": {"small": (10, 10), "large": (5, 5)}}
        good = [
            {"label": "small", "width_px": 10, "height_px": 10, "sha256": "a" * 64},
            {"label": "large", "width_px": 5, "height_px": 5, "sha256": "b" * 64},
        ]
        self.assertEqual(len(check_case_report(case, [{"name": "case", "results": good}])["labels"]), 2)
        for rows in (good[:1], good[:1] * 2, [dict(good[0], width_px=11), good[1]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                check_case_report(case, [{"name": "case", "results": rows}])


if __name__ == "__main__":
    unittest.main()
