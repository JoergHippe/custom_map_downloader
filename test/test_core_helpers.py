import unittest

from test.test_exporter_validation import install_qgis_stubs

install_qgis_stubs()

from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle  # noqa: E402

from custom_map_downloader.core.gdal_io import (  # noqa: E402
    driver_for_output,
    tile_extension_for,
    worldfile_extension_for,
)
from custom_map_downloader.core.models import CenterSpec, ExportParams  # noqa: E402
from custom_map_downloader.core.tiling import pad_extent_to_full_tiles, pick_tile_size  # noqa: E402


class CoreHelperTests(unittest.TestCase):
    def _base_params(self):
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        return ExportParams(
            layer=object(),
            width_px=1000,
            height_px=500,
            gsd_m_per_px=1.0,
            center=CenterSpec(northing=0.0, easting=0.0, crs=crs),
            extent=None,
            output_path="/tmp/out.tif",
            load_as_layer=False,
            render_crs=crs,
            output_crs=crs,
        )

    def test_pick_tile_size_clamps_and_uses_preset(self):
        params = self._base_params()
        params = ExportParams(**{**params.__dict__, "vrt_preset_size": 32})
        self.assertEqual(pick_tile_size(params, default_max_tile_px=2048), (64, 64))

        params = ExportParams(**{**params.__dict__, "vrt_max_cols": 9000, "vrt_max_rows": 512})
        self.assertEqual(pick_tile_size(params, default_max_tile_px=2048), (8192, 512))

    def test_pad_extent_to_full_tiles_expands_symmetrically(self):
        extent = QgsRectangle(0.0, 0.0, 100.0, 50.0)
        padded, width, height = pad_extent_to_full_tiles(
            extent,
            width_px=100,
            height_px=50,
            tile_width_px=64,
            tile_height_px=32,
        )
        self.assertEqual((width, height), (128, 64))
        self.assertAlmostEqual(padded.xMinimum(), -14.0)
        self.assertAlmostEqual(padded.xMaximum(), 114.0)
        self.assertAlmostEqual(padded.yMinimum(), -7.0)
        self.assertAlmostEqual(padded.yMaximum(), 57.0)

    def test_output_driver_and_sidecar_extensions_are_normalized(self):
        self.assertEqual(driver_for_output("a.tiff"), "GTiff")
        self.assertEqual(driver_for_output("a.jpeg"), "JPEG")
        self.assertEqual(tile_extension_for("a.vrt"), ".tif")
        self.assertEqual(tile_extension_for("a.jpeg"), ".jpg")
        self.assertEqual(worldfile_extension_for("a.png"), ".pgw")
        self.assertEqual(worldfile_extension_for("a.jpeg"), ".jgw")


if __name__ == "__main__":
    unittest.main()
