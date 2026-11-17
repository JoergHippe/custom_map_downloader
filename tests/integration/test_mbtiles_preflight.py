"""Real-QGIS checks for MBTiles preflight and mandatory extreme confirmation."""

import importlib
import os
import unittest
from unittest.mock import patch

from tests.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app

try:
    from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer

    ensure_plugin_import_path()
    module = importlib.import_module("custom_map_downloader.CustomMapDownloader")
    from custom_map_downloader.core.models import CenterSpec, ExportParams, ExtentSpec

    HAS_QGIS = True
except Exception:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_QGIS = False


class _Settings:
    def __init__(self):
        self.writes = []

    def value(self, key, default=None, type=None):  # noqa: A002
        # Simulate the user opting out of ordinary export confirmations.
        return False if key.endswith("confirm_export") else default

    def setValue(self, key, value):
        self.writes.append((key, value))


class _MessageBox:
    """Capture the real plugin's confirmation logic without displaying a modal UI."""

    Question = 1
    Yes = 2
    No = 4
    response = No
    created = []

    def __init__(self, icon, title, message, buttons, parent):
        self.message = message
        self.default = None
        self.checkbox = None
        self.created.append(self)

    def setDefaultButton(self, button):
        self.default = button

    def setCheckBox(self, checkbox):
        self.checkbox = checkbox

    def exec(self):
        return self.response


class _Interface:
    def mainWindow(self):
        return None


@unittest.skipUnless(HAS_QGIS, "real QGIS bindings required")
class MbtilesPreflightIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()

    @classmethod
    def tearDownClass(cls):
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def setUp(self):
        _MessageBox.created = []
        _MessageBox.response = _MessageBox.No
        self.settings = _Settings()
        self.plugin = module.CustomMapDownloader(_Interface())
        self.crs = QgsCoordinateReferenceSystem("EPSG:4326")
        self.layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "preflight", "memory")

    def _params(self, zoom_max):
        return ExportParams(
            layer=self.layer,
            width_px=256,
            height_px=256,
            gsd_m_per_px=1.0,
            center=CenterSpec(northing=0, easting=0, crs=self.crs),
            extent=ExtentSpec(
                west=-180, south=-80, east=180, north=80, crs=self.crs
            ),
            output_path="never_written.mbtiles",
            load_as_layer=False,
            mbtiles_zoom_min=0,
            mbtiles_zoom_max=zoom_max,
            mbtiles_tile_size=256,
        )

    def test_extreme_requires_explicit_yes_despite_opt_out(self):
        # A global tile pyramid through zoom 9 has >100,000 tiles.
        params = self._params(9)
        with (
            patch.object(module, "QSettings", return_value=self.settings),
            patch.object(module, "QMessageBox", _MessageBox),
        ):
            self.assertFalse(
                self.plugin._confirm_export(
                    {"layer": self.layer, "output_crs": self.crs}, params
                )
            )
            self.assertEqual(len(_MessageBox.created), 1)
            prompt = _MessageBox.created[0]
            self.assertEqual(prompt.default, _MessageBox.No)
            self.assertIsNone(prompt.checkbox)
            self.assertIn("Tile count", prompt.message)
            self.assertIn("VERY LARGE EXPORT", prompt.message)

            _MessageBox.response = _MessageBox.Yes
            self.assertTrue(
                self.plugin._confirm_export(
                    {"layer": self.layer, "output_crs": self.crs}, params
                )
            )
        self.assertEqual(self.settings.writes, [])

    def test_normal_export_respects_opt_out(self):
        with (
            patch.object(module, "QSettings", return_value=self.settings),
            patch.object(module, "QMessageBox", _MessageBox),
        ):
            self.assertTrue(
                self.plugin._confirm_export(
                    {"layer": self.layer, "output_crs": self.crs}, self._params(0)
                )
            )
        self.assertEqual(_MessageBox.created, [])


if __name__ == "__main__":
    unittest.main()
