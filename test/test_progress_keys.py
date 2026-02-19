import unittest
from pathlib import Path


class ProgressKeysTest(unittest.TestCase):
    """Ensure progress keys used by exporter are present in UI mapping."""

    def test_progress_keys_present_in_plugin(self):
        plugin_path = Path(__file__).parents[1] / "CustomMapDownloader.py"
        text = plugin_path.read_text(encoding="utf-8", errors="replace")

        expected_keys = {
            "STEP_VALIDATE",
            "STEP_PREPARE",
            "STEP_RENDER",
            "STEP_WRITE_RASTER",
            "STEP_WRITE_TIFF",
            "STEP_WRITE_GEOTIFF",
            "STEP_BUILD_VRT",
            "STEP_DONE",
            "WARN_TILE_RETRY",
            "WARN_LARGE_EXPORT",
        }

        missing = [k for k in expected_keys if k not in text]
        self.assertFalse(missing, f"Missing progress keys in CustomMapDownloader.py: {missing}")

    def test_de_qm_exists(self):
        qm_path = Path(__file__).parents[1] / "i18n" / "CustomMapDownloader_de.qm"
        self.assertTrue(qm_path.exists(), "German translation file is missing")


if __name__ == "__main__":
    unittest.main()
