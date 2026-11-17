"""Compare file, pixel and spatial fingerprints on real GDAL GeoTIFFs."""

import os
import tempfile
import unittest
from pathlib import Path

try:
    from osgeo import gdal, osr

    from scripts.raster_diagnostics import inspect_raster

    HAS_GDAL = True
except ImportError:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_GDAL = False


@unittest.skipUnless(HAS_GDAL, "real GDAL Python bindings required")
class RasterDiagnosticsTests(unittest.TestCase):
    def _make_tif(self, path, value, metadata, *, offset=0.0):
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 32, 32, 1, gdal.GDT_Byte)
        self.assertIsNotNone(dataset)
        dataset.SetGeoTransform([500000 + offset, 2.0, 0.0, 5600000, 0.0, -2.0])
        crs = osr.SpatialReference()
        self.assertEqual(crs.ImportFromEPSG(25833), 0)
        dataset.SetProjection(crs.ExportToWkt())
        dataset.SetMetadataItem("RUN_NOTE", metadata)
        band = dataset.GetRasterBand(1)
        self.assertEqual(band.WriteRaster(0, 0, 32, 32, bytes([value]) * 1024), 0)
        band.FlushCache()
        dataset.FlushCache()
        band = None
        dataset = None

    def test_metadata_only_change_keeps_pixels_and_georef(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.tif"
            b = Path(tmp) / "b.tif"
            self._make_tif(a, 42, "old")
            self._make_tif(b, 42, "new")
            previous = inspect_raster(a)
            current = inspect_raster(b)
            self.assertNotEqual(previous["file_sha256"], current["file_sha256"])
            self.assertEqual(previous["pixel_sha256"], current["pixel_sha256"])
            self.assertEqual(previous["georef_sha256"], current["georef_sha256"])
            self.assertNotEqual(
                previous["encoding"]["metadata"], current["encoding"]["metadata"]
            )

    def test_real_pixel_change_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.tif", Path(tmp) / "b.tif"
            self._make_tif(a, 42, "same")
            self._make_tif(b, 43, "same")
            self.assertNotEqual(
                inspect_raster(a)["pixel_sha256"], inspect_raster(b)["pixel_sha256"]
            )

    def test_georeference_change_is_independent_of_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.tif", Path(tmp) / "b.tif"
            self._make_tif(a, 42, "same")
            self._make_tif(b, 42, "same", offset=10.0)
            first, second = inspect_raster(a), inspect_raster(b)
            self.assertEqual(first["pixel_sha256"], second["pixel_sha256"])
            self.assertNotEqual(first["georef_sha256"], second["georef_sha256"])


if __name__ == "__main__":
    unittest.main()
