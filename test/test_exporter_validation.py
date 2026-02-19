import sys
import tempfile
import types
import unittest
from dataclasses import replace
from pathlib import Path


def install_qgis_stubs():
    """Install minimal stub modules for qgis and osgeo to import exporter."""
    # numpy stub (imported by exporter)
    numpy_mod = types.ModuleType("numpy")

    class _DummyArray:
        def __init__(self, *_args, **_kwargs):
            pass

        def reshape(self, *_args, **_kwargs):
            return self

        def max(self):
            return 0

    numpy_mod.uint8 = int
    numpy_mod.float32 = float
    numpy_mod.frombuffer = lambda *_args, **_kwargs: _DummyArray()

    sys.modules["numpy"] = numpy_mod

    # qgis core
    qgis_mod = types.ModuleType("qgis")
    core_mod = types.ModuleType("qgis.core")
    pyqt_mod = types.ModuleType("qgis.PyQt")
    qtcore_mod = types.ModuleType("qgis.PyQt.QtCore")
    qtgui_mod = types.ModuleType("qgis.PyQt.QtGui")

    class DummyDistanceUnit:
        Meters = 1

    class Qgis:
        class DistanceUnit(DummyDistanceUnit):
            pass

    class QgsUnitTypes:
        @staticmethod
        def toString(_units):
            return "meters"

    class QgsCoordinateReferenceSystem:
        def __init__(self, authid=""):
            self._authid = authid

        def isValid(self):
            return True

        def mapUnits(self):
            return DummyDistanceUnit.Meters

        def authid(self):
            return self._authid

        def toWkt(self):
            return "WKT"

        def __eq__(self, other):
            return isinstance(other, QgsCoordinateReferenceSystem) and self._authid == other._authid

    class QgsRectangle:
        def __init__(self, xmin=0, ymin=0, xmax=1, ymax=1):
            self._xmin, self._ymin, self._xmax, self._ymax = xmin, ymin, xmax, ymax

        def width(self):
            return self._xmax - self._xmin

        def height(self):
            return self._ymax - self._ymin

        def xMinimum(self):
            return self._xmin

        def xMaximum(self):
            return self._xmax

        def yMinimum(self):
            return self._ymin

        def yMaximum(self):
            return self._ymax

        def isEmpty(self):
            return self.width() <= 0 or self.height() <= 0

    class QgsPointXY:
        def __init__(self, x, y):
            self._x, self._y = x, y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class QgsCoordinateTransform:
        def __init__(self, *_args, **_kwargs):
            pass

        def transformBoundingBox(self, rect):
            return rect

        def transform(self, point):
            return point

    class QgsProject:
        _instance = None

        @classmethod
        def instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

        def crs(self):
            return QgsCoordinateReferenceSystem("EPSG:3857")

    class QgsMapSettings:
        pass

    class QgsMapLayer:
        RasterLayer = 1

    class QgsMapRendererParallelJob:
        def __init__(self, *_args, **_kwargs):
            pass

    class QColor:
        def __init__(self, *_args, **_kwargs):
            pass

    class QImage:
        Format_RGBA8888 = 0

    class QCoreApplication:
        @staticmethod
        def translate(_context, message):
            return message

    class QSize:
        def __init__(self, *_args, **_kwargs):
            pass

    core_mod.Qgis = Qgis
    core_mod.QgsUnitTypes = QgsUnitTypes
    core_mod.QgsCoordinateReferenceSystem = QgsCoordinateReferenceSystem
    core_mod.QgsCoordinateTransform = QgsCoordinateTransform
    core_mod.QgsMapLayer = QgsMapLayer
    core_mod.QgsMapRendererParallelJob = QgsMapRendererParallelJob
    core_mod.QgsMapSettings = QgsMapSettings
    core_mod.QgsPointXY = QgsPointXY
    core_mod.QgsProject = QgsProject
    core_mod.QgsRectangle = QgsRectangle

    qtcore_mod.QCoreApplication = QCoreApplication
    qtcore_mod.QSize = QSize
    qtgui_mod.QColor = QColor
    qtgui_mod.QImage = QImage

    qgis_mod.core = core_mod
    qgis_mod.PyQt = pyqt_mod
    pyqt_mod.QtCore = qtcore_mod
    pyqt_mod.QtGui = qtgui_mod

    sys.modules["qgis"] = qgis_mod
    sys.modules["qgis.core"] = core_mod
    sys.modules["qgis.PyQt"] = pyqt_mod
    sys.modules["qgis.PyQt.QtCore"] = qtcore_mod
    sys.modules["qgis.PyQt.QtGui"] = qtgui_mod

    # osgeo stubs
    osgeo_mod = types.ModuleType("osgeo")
    gdal_mod = types.ModuleType("osgeo.gdal")
    osr_mod = types.ModuleType("osgeo.osr")

    class DummyDriver:
        def Create(self, *_args, **_kwargs):
            return object()

    class gdal:
        GDT_Byte = 1

        @staticmethod
        def GetDriverByName(_name):
            return DummyDriver()

        @staticmethod
        def BuildVRT(_path, _tiles):
            return object()

    class osr:
        class SpatialReference:
            def ImportFromEPSG(self, *_args):
                return 0

            def ExportToWkt(self):
                return "WKT"

            def ImportFromWkt(self, *_args):
                return 0

    gdal_mod.GDT_Byte = gdal.GDT_Byte
    gdal_mod.GetDriverByName = gdal.GetDriverByName
    gdal_mod.BuildVRT = gdal.BuildVRT
    osr_mod.SpatialReference = osr.SpatialReference

    osgeo_mod.gdal = gdal_mod
    osgeo_mod.osr = osr_mod

    sys.modules["osgeo"] = osgeo_mod
    sys.modules["osgeo.gdal"] = gdal_mod
    sys.modules["osgeo.osr"] = osr_mod


install_qgis_stubs()

import qgis  # noqa: E402
from core.constants import GSD_MIN, GSD_MAX, LARGE_RASTER_STRONG_MAX_DIM_PX  # noqa: E402
from core.errors import ValidationError  # noqa: E402
from core.exporter import GeoTiffExporter  # noqa: E402
from core.models import CenterSpec, ExportParams, ExtentSpec  # noqa: E402


class ExporterValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.out_dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def _base_params(self, *, width=1000, height=1000, path_suffix=".tif") -> ExportParams:
        crs = qgis.core.QgsCoordinateReferenceSystem("EPSG:3857")
        return ExportParams(
            layer=object(),
            width_px=width,
            height_px=height,
            gsd_m_per_px=1.0,
            center=CenterSpec(northing=0.0, easting=0.0, crs=crs),
            extent=ExtentSpec(west=0.0, south=0.0, east=10.0, north=10.0, crs=crs),
            output_path=str(self.out_dir / f"out{path_suffix}"),
            load_as_layer=False,
            render_crs=crs,
            output_crs=crs,
        )

    def test_rejects_too_large_raster(self):
        large = LARGE_RASTER_STRONG_MAX_DIM_PX
        params = self._base_params(width=large, height=large)
        exporter = GeoTiffExporter()

        with self.assertRaises(ValidationError) as ctx:
            exporter._validate(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_SIZE_TOO_LARGE")

    def test_rejects_unsupported_extension(self):
        params = self._base_params(path_suffix=".txt")
        exporter = GeoTiffExporter()

        with self.assertRaises(ValidationError) as ctx:
            exporter._validate(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_OUTPUT_EXT")

    def test_rejects_missing_directory(self):
        params = self._base_params()
        params = replace(params, output_path=str(Path(self.out_dir, "missing_dir", "out.tif")))
        exporter = GeoTiffExporter()

        with self.assertRaises(ValidationError) as ctx:
            exporter._validate(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_OUTPUT_DIR")

    def test_rejects_gsd_below_min(self):
        params = self._base_params()
        params = replace(params, gsd_m_per_px=GSD_MIN / 10)
        exporter = GeoTiffExporter()

        with self.assertRaises(ValidationError) as ctx:
            exporter._validate(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_GSD_INVALID")

    def test_rejects_gsd_above_max(self):
        params = self._base_params()
        params = replace(params, gsd_m_per_px=GSD_MAX * 10)
        exporter = GeoTiffExporter()

        with self.assertRaises(ValidationError) as ctx:
            exporter._validate(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_GSD_INVALID")

    def test_pick_tile_size_prefers_user_values_and_presets(self):
        exporter = GeoTiffExporter()
        params = self._base_params()

        # explicit max cols/rows
        params_with_max = replace(params, vrt_max_cols=512, vrt_max_rows=256, vrt_preset_size=2048)
        tw, th = exporter._pick_tile_size(params_with_max)
        self.assertEqual((tw, th), (512, 256))

        # fallback to preset when max values are zero
        params_with_preset = replace(params, vrt_max_cols=0, vrt_max_rows=0, vrt_preset_size=2048)
        tw, th = exporter._pick_tile_size(params_with_preset)
        self.assertEqual((tw, th), (2048, 2048))


if __name__ == "__main__":
    unittest.main()
