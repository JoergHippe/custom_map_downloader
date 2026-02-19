import unittest
import sys
import types

from core.constants import GSD_MIN, GSD_MAX, LARGE_RASTER_STRONG_MAX_DIM_PX, LARGE_RASTER_STRONG_TOTAL_PX
from core.errors import ValidationError


def install_qgis_stubs():
    """Install minimal qgis.core stubs needed by core.validation imports."""
    qgis_mod = types.ModuleType("qgis")
    core_mod = types.ModuleType("qgis.core")

    class Qgis:
        class DistanceUnit:
            Meters = 1

    class QgsUnitTypes:
        @staticmethod
        def toString(_units):
            return "meters"

    class QgsCoordinateReferenceSystem:
        def mapUnits(self):
            return Qgis.DistanceUnit.Meters

    core_mod.Qgis = Qgis
    core_mod.QgsUnitTypes = QgsUnitTypes
    core_mod.QgsCoordinateReferenceSystem = QgsCoordinateReferenceSystem

    qgis_mod.core = core_mod
    sys.modules["qgis"] = qgis_mod
    sys.modules["qgis.core"] = core_mod


install_qgis_stubs()

from core.validation import validate_gsd, validate_pixel_limits, validate_output_path


class ValidationHelpersTests(unittest.TestCase):
    def test_validate_gsd_ok(self):
        validate_gsd(GSD_MIN)
        validate_gsd((GSD_MIN + GSD_MAX) / 2.0)
        validate_gsd(GSD_MAX)

    def test_validate_gsd_invalid(self):
        for gsd in (-1.0, 0.0, GSD_MIN / 10, GSD_MAX * 10):
            with self.assertRaises(ValidationError):
                validate_gsd(gsd)

    def test_validate_pixel_limits_invalid(self):
        with self.assertRaises(ValidationError):
            validate_pixel_limits(LARGE_RASTER_STRONG_MAX_DIM_PX, 10)
        with self.assertRaises(ValidationError):
            validate_pixel_limits(10, LARGE_RASTER_STRONG_MAX_DIM_PX)
        too_many = LARGE_RASTER_STRONG_TOTAL_PX + 1
        side = int(too_many ** 0.5) + 1
        with self.assertRaises(ValidationError):
            validate_pixel_limits(side, side)

    def test_validate_output_path_invalid(self):
        with self.assertRaises(ValidationError):
            validate_output_path("")
        with self.assertRaises(ValidationError):
            validate_output_path("/nonexistent/path/file.tif")
        with self.assertRaises(ValidationError):
            validate_output_path("/tmp/file.unsupported")


if __name__ == "__main__":
    unittest.main()
