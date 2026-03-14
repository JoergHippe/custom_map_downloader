import json
import tempfile
import unittest
from pathlib import Path

from scripts import probe_windows_scale_case, run_windows_qgis_matrix


class WindowsQgisMatrixScriptTests(unittest.TestCase):
    def test_read_scale_case_names_uses_requested_matrix_key(self):
        config = {
            "scale_matrix": [{"name": "stable_case"}],
            "experimental_scale_matrix": [{"name": "experimental_case"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            original_config_path = run_windows_qgis_matrix.CONFIG_PATH
            run_windows_qgis_matrix.CONFIG_PATH = config_path
            try:
                stable = run_windows_qgis_matrix.read_scale_case_names("scale_matrix")
                experimental = run_windows_qgis_matrix.read_scale_case_names(
                    "experimental_scale_matrix"
                )
            finally:
                run_windows_qgis_matrix.CONFIG_PATH = original_config_path

        self.assertEqual(stable, ["stable_case"])
        self.assertEqual(experimental, ["experimental_case"])

    def test_probe_loader_reads_cases_from_requested_matrix_key(self):
        config = {
            "scale_matrix": [{"name": "stable_case"}],
            "experimental_scale_matrix": [{"name": "experimental_case"}],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            original_config_path = probe_windows_scale_case.CONFIG_PATH
            probe_windows_scale_case.CONFIG_PATH = config_path
            try:
                cases = probe_windows_scale_case.load_case_names("experimental_scale_matrix")
            finally:
                probe_windows_scale_case.CONFIG_PATH = original_config_path

        self.assertEqual(list(cases), ["experimental_case"])

    def test_probe_metadata_includes_dimensions_and_tiling_expectation(self):
        case = {
            "extent": {"west": 0, "east": 1000, "south": 0, "north": 1000},
            "small_scale": 1500,
            "large_scale": 10000,
        }

        small = probe_windows_scale_case.build_probe_metadata(case, "small")
        large = probe_windows_scale_case.build_probe_metadata(case, "large")

        self.assertEqual(small["scale"], 1500.0)
        self.assertEqual(large["scale"], 10000.0)
        self.assertTrue(small["width_px"] > large["width_px"])
        self.assertTrue(small["expected_tiling"])
        self.assertFalse(large["expected_tiling"])


if __name__ == "__main__":
    unittest.main()
