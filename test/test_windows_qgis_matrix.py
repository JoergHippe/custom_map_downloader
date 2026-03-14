import json
import tempfile
import unittest
from pathlib import Path

from scripts import run_windows_qgis_matrix


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


if __name__ == "__main__":
    unittest.main()
