"""Network-free MBTiles export integration using real QGIS bindings."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsFillSymbol,
        QgsGeometry,
        QgsProject,
        QgsRectangle,
        QgsVectorLayer,
    )

    ensure_plugin_import_path()
    from custom_map_downloader.core.errors import CancelledError
    from custom_map_downloader.core.exporter import GeoTiffExporter
    from custom_map_downloader.core.models import (
        CancelToken,
        CenterSpec,
        ExportParams,
        ExtentSpec,
    )

    HAS_QGIS = True
except Exception:
    # A missing real QGIS runtime must be a hard failure in QGIS CI.
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_QGIS = False


@unittest.skipUnless(HAS_QGIS, "real QGIS bindings required")
class MbtilesExportIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()
        cls.project = QgsProject.instance()

    @classmethod
    def tearDownClass(cls):
        cls.project.removeAllMapLayers()
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "existing.mbtiles"

        # A local polygon covers enough pixels of the global z0 tile to
        # render visible PNG content without contacting a map service.
        self.layer = QgsVectorLayer("Polygon?crs=EPSG:3857", "mbtiles_test", "memory")
        self.assertTrue(self.layer.isValid())
        feature = QgsFeature()
        feature.setGeometry(
            QgsGeometry.fromRect(
                QgsRectangle(-15000000, -15000000, 15000000, 15000000)
            )
        )
        added, _ = self.layer.dataProvider().addFeatures([feature])
        self.assertTrue(added)
        self.layer.updateExtents()
        self.layer.renderer().setSymbol(
            QgsFillSymbol.createSimple(
                {"color": "20,100,180,255", "outline_style": "no"}
            )
        )
        self.project.addMapLayer(self.layer)
        self.addCleanup(self.project.removeMapLayer, self.layer.id())

    def _params(self):
        crs_3857 = QgsCoordinateReferenceSystem("EPSG:3857")
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        return ExportParams(
            layer=self.layer,
            width_px=128,
            height_px=128,
            gsd_m_per_px=1.0,
            center=CenterSpec(northing=0, easting=0, crs=crs_3857),
            extent=ExtentSpec(
                west=-180,
                south=-80,
                east=180,
                north=80,
                crs=crs_4326,
            ),
            output_path=str(self.target),
            load_as_layer=False,
            mbtiles_zoom_min=0,
            mbtiles_zoom_max=0,
            mbtiles_tile_size=128,
        )

    def test_existing_mbtiles_is_replaced_after_success(self):
        self.target.write_bytes(b"prior export")
        result = GeoTiffExporter().export(self._params())
        self.assertEqual(result, str(self.target))

        with sqlite3.connect(self.target) as conn:
            tiles = conn.execute("SELECT tile_data FROM tiles").fetchall()
            metadata = dict(conn.execute("SELECT name, value FROM metadata"))
        self.assertEqual(len(tiles), 1)
        self.assertTrue(tiles[0][0].startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(metadata["format"], "png")
        self.assertEqual(
            sorted(p.name for p in self.target.parent.iterdir()), [self.target.name]
        )

    def test_cancel_mid_export_preserves_existing_mbtiles(self):
        original = b"prior export"
        self.target.write_bytes(original)
        token = CancelToken()

        def cancel_after_database_is_open(_percent, key, _args):
            # STEP_RENDER occurs after creating the staged SQLite database.
            if key == "STEP_RENDER":
                token.cancel()

        with self.assertRaises(CancelledError):
            GeoTiffExporter().export(
                self._params(),
                progress_cb=cancel_after_database_is_open,
                cancel_token=token,
            )
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(
            sorted(p.name for p in self.target.parent.iterdir()), [self.target.name]
        )


if __name__ == "__main__":
    unittest.main()
