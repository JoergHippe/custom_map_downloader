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
            return DummyWritableDataset()

    class DummyBand:
        def WriteArray(self, *_args, **_kwargs):
            return None

        def SetNoDataValue(self, *_args, **_kwargs):
            return None

        def FlushCache(self):
            return None

    class DummyWritableDataset:
        def SetGeoTransform(self, *_args, **_kwargs):
            return None

        def SetProjection(self, *_args, **_kwargs):
            return None

        def GetRasterBand(self, *_args, **_kwargs):
            return DummyBand()

        def FlushCache(self):
            return None

    class DummyWarpDataset:
        RasterXSize = 256
        RasterYSize = 128

        def GetGeoTransform(self):
            return [1.0, 2.0, 0.0, 3.0, 0.0, -2.0]

        def FlushCache(self):
            return None

    class gdal:
        GDT_Byte = 1

        @staticmethod
        def GetDriverByName(_name):
            return DummyDriver()

        @staticmethod
        def BuildVRT(_path, _tiles):
            return object()

        @staticmethod
        def Open(_path):
            return DummyWarpDataset()

        @staticmethod
        def Warp(_dst, _src, **_kwargs):
            return DummyWarpDataset()

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
    gdal_mod.Open = gdal.Open
    gdal_mod.Warp = gdal.Warp
    osr_mod.SpatialReference = osr.SpatialReference

    osgeo_mod.gdal = gdal_mod
    osgeo_mod.osr = osr_mod

    sys.modules["osgeo"] = osgeo_mod
    sys.modules["osgeo.gdal"] = gdal_mod
    sys.modules["osgeo.osr"] = osr_mod


install_qgis_stubs()

import qgis  # noqa: E402

from custom_map_downloader.core.constants import (  # noqa: E402
    GSD_MAX,
    GSD_MIN,
    LARGE_RASTER_STRONG_MAX_DIM_PX,
)
from custom_map_downloader.core.errors import ValidationError  # noqa: E402
from custom_map_downloader.core.exporter import GeoTiffExporter  # noqa: E402
from custom_map_downloader.core.models import CenterSpec, ExportParams, ExtentSpec  # noqa: E402


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

    def test_rejects_vrt_with_different_render_and_output_crs(self):
        exporter = GeoTiffExporter()
        params = replace(
            self._base_params(path_suffix=".vrt"),
            create_vrt=True,
            output_crs=qgis.core.QgsCoordinateReferenceSystem("EPSG:4326"),
        )

        with self.assertRaises(ValidationError) as ctx:
            exporter.export(params)

        self.assertEqual(ctx.exception.code, "ERR_VALIDATION_VRT_OUTPUT_CRS_UNSUPPORTED")

    def test_warp_rendered_raster_writes_output_sidecars(self):
        exporter = GeoTiffExporter()
        render_crs = qgis.core.QgsCoordinateReferenceSystem("EPSG:3857")
        output_crs = qgis.core.QgsCoordinateReferenceSystem("EPSG:4326")
        output_path = self.out_dir / "warped_output.tif"

        result = exporter._warp_rendered_raster(
            str(self.out_dir / "intermediate.tif"),
            final_output_path=str(output_path),
            render_extent=qgis.core.QgsRectangle(0.0, 0.0, 10.0, 10.0),
            render_crs=render_crs,
            output_crs=output_crs,
            progress_cb=None,
            cancel_token=None,
        )

        self.assertEqual(result, str(output_path))
        self.assertTrue((self.out_dir / "warped_output.tfw").exists())
        self.assertTrue((self.out_dir / "warped_output.prj").exists())

    def test_default_render_crs_falls_back_when_project_instance_is_missing(self):
        exporter = GeoTiffExporter()
        original_instance = qgis.core.QgsProject.instance
        qgis.core.QgsProject.instance = classmethod(lambda cls: None)
        try:
            crs = exporter._default_render_crs()
        finally:
            qgis.core.QgsProject.instance = original_instance

        self.assertEqual(crs.authid(), "EPSG:3857")

    def test_vrt_relative_path_failure_emits_warning_and_still_succeeds(self):
        exporter = GeoTiffExporter()
        params = replace(
            self._base_params(path_suffix=".vrt"),
            create_vrt=True,
            vrt_max_cols=256,
            vrt_max_rows=256,
        )
        original_make_relative = exporter._make_vrt_paths_relative
        original_render_tile = exporter._render_tile_rgba
        original_wait = exporter._wait_with_events
        progress_events = []

        def fail_make_relative(_vrt_path, _tile_paths):
            raise RuntimeError("rewrite failed")

        class FakeArray:
            def __getitem__(self, _key):
                return self

            def max(self):
                return 255

        def fake_render_tile_rgba(**_kwargs):
            return FakeArray()

        exporter._make_vrt_paths_relative = fail_make_relative
        exporter._render_tile_rgba = fake_render_tile_rgba
        exporter._wait_with_events = lambda *_args, **_kwargs: None
        try:
            result = exporter.export(
                params,
                progress_cb=lambda percent, key, args: progress_events.append((percent, key, args)),
            )
        finally:
            exporter._make_vrt_paths_relative = original_make_relative
            exporter._render_tile_rgba = original_render_tile
            exporter._wait_with_events = original_wait

        self.assertTrue(result.endswith(".vrt"))
        self.assertTrue(any(key == "WARN_VRT_ABSOLUTE_PATHS" for _, key, _ in progress_events))

    def test_tiled_png_uses_intermediate_gtiff_conversion(self):
        exporter = GeoTiffExporter()
        params = self._base_params(width=5000, height=5000, path_suffix=".png")

        calls = {"tiled": 0, "warp": 0}
        original_export_tiled = exporter._export_tiled
        original_warp = exporter._warp_rendered_raster

        def fake_export_tiled(*args, **kwargs):
            calls["tiled"] += 1
            output_path = (
                kwargs["params"].output_path if "params" in kwargs else args[0].output_path
            )
            Path(output_path).write_bytes(b"fake-tiff")
            return output_path

        def fake_warp(source_path, **kwargs):
            calls["warp"] += 1
            self.assertTrue(str(source_path).endswith(".tif"))
            final_output = kwargs["final_output_path"]
            Path(final_output).write_bytes(b"fake-png")
            return final_output

        exporter._export_tiled = fake_export_tiled
        exporter._warp_rendered_raster = fake_warp
        try:
            result = exporter.export(params)
        finally:
            exporter._export_tiled = original_export_tiled
            exporter._warp_rendered_raster = original_warp

        self.assertEqual(result, params.output_path)
        self.assertEqual(calls["tiled"], 1)
        self.assertEqual(calls["warp"], 1)

    def test_web_map_layer_forces_tiled_path_even_below_tile_limit(self):
        exporter = GeoTiffExporter()

        class FakeLayer:
            def providerType(self):
                return "wms"

            def source(self):
                return "url=https://example.test/wms"

        params = replace(
            self._base_params(width=595, height=595, path_suffix=".tif"),
            layer=FakeLayer(),
        )

        calls = {"tiled": 0}
        original_export_tiled = exporter._export_tiled

        def fake_export_tiled(*args, **kwargs):
            calls["tiled"] += 1
            output_path = (
                kwargs["params"].output_path if "params" in kwargs else args[0].output_path
            )
            Path(output_path).write_bytes(b"fake-tif")
            return output_path

        exporter._export_tiled = fake_export_tiled
        try:
            result = exporter.export(params)
        finally:
            exporter._export_tiled = original_export_tiled

        self.assertEqual(result, params.output_path)
        self.assertEqual(calls["tiled"], 1)

    def test_non_scale_sensitive_layer_keeps_direct_path_below_tile_limit(self):
        exporter = GeoTiffExporter()

        class FakeLayer:
            def providerType(self):
                return "gdal"

            def source(self):
                return "/tmp/local.tif"

        params = replace(
            self._base_params(width=595, height=595, path_suffix=".tif"),
            layer=FakeLayer(),
            target_scale_denominator=6000.0,
        )

        original_create_dataset = exporter._gdal_create_dataset
        original_render_tile = exporter._render_tile_rgba
        original_wait = exporter._wait_with_events
        calls = {"direct_write": 0, "tile_render": 0}

        class FakeDataset:
            def SetGeoTransform(self, *_args, **_kwargs):
                return None

            def SetProjection(self, *_args, **_kwargs):
                return None

            def GetRasterBand(self, *_args, **_kwargs):
                class FakeBand:
                    def WriteArray(self, *_args, **_kwargs):
                        return None

                    def FlushCache(self):
                        return None

                return FakeBand()

        class FakeRenderedImage:
            def convertToFormat(self, *_args, **_kwargs):
                return self

            def bits(self):
                class _Bits:
                    def setsize(self, *_args, **_kwargs):
                        return None

                return _Bits()

            def sizeInBytes(self):
                return 4

        class FakeRenderJob:
            def start(self):
                return None

            def isActive(self):
                return False

            def waitForFinished(self):
                return None

            def renderedImage(self):
                return FakeRenderedImage()

        class FakeMapSettings:
            def setBackgroundColor(self, *_args, **_kwargs):
                return None

            def setLayers(self, *_args, **_kwargs):
                return None

            def setExtent(self, *_args, **_kwargs):
                return None

            def setOutputSize(self, *_args, **_kwargs):
                return None

            def setDestinationCrs(self, *_args, **_kwargs):
                return None

            def setOutputDpi(self, *_args, **_kwargs):
                return None

        def fake_create_dataset(**_kwargs):
            return FakeDataset()

        def fake_qimage_to_rgba_array(*_args, **_kwargs):
            class FakeArray:
                ndim = 3
                shape = (1, 1, 4)

                def __getitem__(self, _key):
                    return self

                def astype(self, *_args, **_kwargs):
                    return self

                def max(self):
                    return 255

            return FakeArray()

        exporter._gdal_create_dataset = fake_create_dataset
        exporter._render_tile_rgba = lambda **_kwargs: calls.__setitem__("tile_render", 1)
        exporter._wait_with_events = lambda *_args, **_kwargs: None

        import custom_map_downloader.core.exporter as exporter_module

        original_renderer_cls = exporter_module.QgsMapRendererParallelJob
        original_map_settings_cls = exporter_module.QgsMapSettings
        original_qimage_to_rgba_array = exporter_module.qimage_to_rgba_array
        original_write_full_raster_fn = exporter_module.write_full_raster
        exporter_module.QgsMapRendererParallelJob = lambda *_args, **_kwargs: FakeRenderJob()
        exporter_module.QgsMapSettings = FakeMapSettings
        exporter_module.qimage_to_rgba_array = fake_qimage_to_rgba_array
        exporter_module.write_full_raster = lambda **_kwargs: calls.__setitem__(
            "direct_write", calls["direct_write"] + 1
        )
        try:
            result = exporter.export(params)
        finally:
            exporter._gdal_create_dataset = original_create_dataset
            exporter._render_tile_rgba = original_render_tile
            exporter._wait_with_events = original_wait
            exporter_module.QgsMapRendererParallelJob = original_renderer_cls
            exporter_module.QgsMapSettings = original_map_settings_cls
            exporter_module.qimage_to_rgba_array = original_qimage_to_rgba_array
            exporter_module.write_full_raster = original_write_full_raster_fn

        self.assertEqual(result, params.output_path)
        self.assertEqual(calls["direct_write"], 1)
        self.assertEqual(calls["tile_render"], 0)


if __name__ == "__main__":
    unittest.main()
