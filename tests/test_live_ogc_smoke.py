"""Fail-closed validation for the opt-in public WMS smoke runner."""

import json
import unittest
from pathlib import Path

from scripts.run_live_ogc_smoke import check_live_report, load_scenario

CONFIG = json.loads(
    (Path(__file__).resolve().parents[1] / "tests" / "integration" / "config.json").read_text(
        encoding="utf-8"
    )
)


class LiveServiceSmokeTests(unittest.TestCase):
    def test_existing_small_official_scenario(self):
        candidate = load_scenario(CONFIG, "bkg_dgm200_relief_tif", 2_000_000)
        self.assertEqual(candidate["provider"], "wms")
        self.assertLessEqual(candidate["width_px"] * candidate["height_px"], 2_000_000)

    def test_unknown_scenario_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            load_scenario(CONFIG, "unknown_service", 2_000_000)

    def test_oversized_raster_is_rejected_before_network(self):
        with self.assertRaises(ValueError):
            load_scenario(CONFIG, "geosn_ortho_color", 100)

    def test_network_result_must_be_present_and_successful(self):
        good = {
            "name": "official",
            "result": "ok",
            "width_px": 200,
            "height_px": 250,
            "sha256": "a" * 64,
        }
        self.assertEqual(check_live_report([good], "official"), "a" * 64)
        for rows in (
            [],
            [dict(good, result="error")],
            [dict(good, name="different")],
            [dict(good, sha256="invalid")],
            [good, good],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                check_live_report(rows, "official")


if __name__ == "__main__":
    unittest.main()
