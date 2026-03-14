import tempfile
import unittest
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from test.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app


def _resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _resolve_repo_root()
TEST_DATA = REPO_ROOT / "test" / "tenbytenraster.asc"

warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo.gdal")
warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo")

if TYPE_CHECKING:
    from qgis.core import (
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
    )
else:
    QgsApplication = object  # type: ignore
    QgsCoordinateReferenceSystem = object  # type: ignore
    QgsProject = object  # type: ignore
    QgsRasterLayer = object  # type: ignore

try:
    from qgis.core import (  # type: ignore
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
    )

    ensure_plugin_import_path()

    from custom_map_downloader.core.exporter import GeoTiffExporter  # type: ignore
    from custom_map_downloader.core.models import (  # type: ignore
        CenterSpec,
        ExportParams,
        ExtentSpec,
    )
    from custom_map_downloader.core.scale import (  # type: ignore
        OGC_STANDARD_DPI,
        gsd_to_scale_denominator,
    )

    HAS_QGIS = True
except Exception:
    HAS_QGIS = False
    OGC_STANDARD_DPI = 0.0  # type: ignore
    gsd_to_scale_denominator = None  # type: ignore
else:
    warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo.gdal")


@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping integration test")
class QgisExportIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()
        cls.project = QgsProject.instance()

    @classmethod
    def tearDownClass(cls):
        if not HAS_QGIS:
            return
        try:
            cls.project.removeAllMapLayers()
        except Exception:
            pass
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def _export_test_raster(
        self,
        output_name: str,
        *,
        target_scale: bool,
        create_vrt: bool = False,
        output_crs_authid: str = "EPSG:3857",
    ) -> str:
        if not TEST_DATA.exists():
            self.skipTest("Test raster not found")

        layer = QgsRasterLayer(str(TEST_DATA), output_name)
        self.assertTrue(layer.isValid(), "Raster layer failed to load")

        metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        output_crs = QgsCoordinateReferenceSystem(output_crs_authid)
        layer.setCrs(metric_crs)
        self.project.addMapLayer(layer)

        extent = layer.extent()
        center = extent.center()
        output_suffix = ".vrt" if create_vrt else ".tif"
        output_path = Path(tempfile.gettempdir()) / f"{output_name}{output_suffix}"
        if output_path.exists():
            output_path.unlink()

        params = ExportParams(
            layer=layer,
            width_px=10,
            height_px=10,
            gsd_m_per_px=10.0,
            center=CenterSpec(northing=center.y(), easting=center.x(), crs=metric_crs),
            extent=ExtentSpec(
                west=extent.xMinimum(),
                south=extent.yMinimum(),
                east=extent.xMaximum(),
                north=extent.yMaximum(),
                crs=metric_crs,
            ),
            output_path=str(output_path),
            load_as_layer=False,
            render_crs=metric_crs,
            output_crs=output_crs,
            target_scale_denominator=gsd_to_scale_denominator(10.0) if target_scale else None,
            output_dpi=OGC_STANDARD_DPI if target_scale else None,
            create_vrt=create_vrt,
            vrt_max_cols=16 if create_vrt else 0,
            vrt_max_rows=16 if create_vrt else 0,
            vrt_preset_size=16 if create_vrt else 0,
        )

        try:
            result_path = GeoTiffExporter().export(params)
            self.assertTrue(Path(result_path).exists(), "Exported file not found")
            return result_path
        finally:
            try:
                self.project.removeMapLayer(layer.id())
            except Exception:
                pass

    def test_export_small_raster(self):
        output_path = Path(self._export_test_raster("cmd_integration_export", target_scale=False))
        self.assertTrue(output_path.exists())
        output_path.unlink()

    def test_export_small_raster_with_target_scale(self):
        output_path = Path(
            self._export_test_raster("cmd_integration_export_scale", target_scale=True)
        )
        self.assertTrue(output_path.exists())
        output_path.unlink()

    def test_export_small_raster_as_vrt(self):
        output_path = Path(
            self._export_test_raster(
                "cmd_integration_export_vrt",
                target_scale=False,
                create_vrt=True,
            )
        )
        self.assertTrue(output_path.exists())
        tile_paths = list(output_path.parent.glob("cmd_integration_export_vrt__tile_*.tif"))
        self.assertTrue(tile_paths, "Expected VRT tile outputs")
        output_path.unlink()
        for tile_path in tile_paths:
            tile_path.unlink()
            for suffix in (".tfw", ".prj"):
                sidecar = tile_path.with_suffix(suffix)
                if sidecar.exists():
                    sidecar.unlink()

    def test_export_small_raster_with_reprojection(self):
        output_path = Path(
            self._export_test_raster(
                "cmd_integration_export_warp",
                target_scale=False,
                create_vrt=False,
                output_crs_authid="EPSG:4326",
            )
        )
        self.assertTrue(output_path.exists())
        self.assertTrue(output_path.with_suffix(".tfw").exists())
        self.assertTrue(output_path.with_suffix(".prj").exists())
        output_path.unlink()
        output_path.with_suffix(".tfw").unlink()
        output_path.with_suffix(".prj").unlink()


if __name__ == "__main__":
    unittest.main()
