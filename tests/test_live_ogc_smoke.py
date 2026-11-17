"""Fail-closed validation for the opt-in public WMS smoke runner."""

import json
import unittest
from pathlib import Path

from scripts.run_live_ogc_smoke import (
    check_live_report,
    classify_reference,
    check_raster_diagnostics,
    load_scenario,
)

CONFIG = json.loads(
    (Path(__file__).resolve().parents[1] / "tests" / "integration" / "config.json").read_text(
        encoding="utf-8"
    )
)


class LiveServiceSmokeTests(unittest.TestCase):
    def test_reference_changes_are_informational(self):
        self.assertEqual(classify_reference("new", "old"), "drift")
        self.assertEqual(classify_reference("same", "same"), "match")
        self.assertEqual(classify_reference("new", None), "untracked")

    def test_existing_small_official_scenario(self):
        candidate = load_scenario(CONFIG, "bkg_dgm200_relief_tif", 2_000_000)
        self.assertEqual(candidate["provider"], "wms")
        self.assertLessEqual(candidate["width_px"] * candidate["height_px"], 2_000_000)
        self.assertEqual(len(candidate["reference_sha256"]), 64)

    def test_unknown_scenario_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            load_scenario(CONFIG, "unknown_service", 2_000_000)

    def test_oversized_raster_is_rejected_before_network(self):
        with self.assertRaises(ValueError):
            load_scenario(CONFIG, "geosn_ortho_color", 100)

    def test_live_geotiff_report_requires_separate_fingerprints(self):
        file_hash = "a" * 64
        diagnostics = {
            "file_sha256": file_hash,
            "pixel_sha256": "b" * 64,
            "georef_sha256": "c" * 64,
            "georeference": {"width": 100, "height": 100},
            "encoding": {"gdal_version": "3.10"},
        }
        self.assertEqual(check_raster_diagnostics(diagnostics, file_hash), diagnostics)
        for invalid in (
            None,
            dict(diagnostics, pixel_sha256="invalid"),
            dict(diagnostics, georef_sha256="x" * 64),
            dict(diagnostics, file_sha256="d" * 64),
            dict(diagnostics, georeference=None),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                check_raster_diagnostics(invalid, file_hash)

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
