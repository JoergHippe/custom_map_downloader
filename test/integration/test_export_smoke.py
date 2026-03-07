import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from custom_map_downloader.core.scale import OGC_STANDARD_DPI, gsd_to_scale_denominator


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


def _detect_qgis_prefix() -> str:
    """Best-effort QGIS-Prefix finden (Env bevorzugt)."""
    prefix_env = os.environ.get("QGIS_PREFIX_PATH", "").strip()
    qgis_runtime_prefix = ""
    try:
        qgis_runtime_prefix = str(QgsApplication.prefixPath() or "").strip()
    except Exception:
        qgis_runtime_prefix = ""
    candidates = [
        prefix_env,
        qgis_runtime_prefix,
        "/usr",
        "/usr/local",
        "/usr/lib/qgis",
        r"C:\OSGeo4W64\apps\qgis",
        r"C:\OSGeo4W\apps\qgis",
        r"C:\Program Files\QGIS 3.36.0\apps\qgis",
        r"C:\Program Files\QGIS 3.34.0\apps\qgis",
    ]
    return next((p for p in candidates if p and Path(p).exists()), "")


try:
    from qgis.core import (  # type: ignore
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
    )

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from custom_map_downloader.core.exporter import GeoTiffExporter  # type: ignore
    from custom_map_downloader.core.models import (  # type: ignore
        CenterSpec,
        ExportParams,
        ExtentSpec,
    )

    HAS_QGIS = True
except Exception:
    HAS_QGIS = False
else:
    warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo.gdal")


def _init_qgis_app() -> Tuple[Optional["QgsApplication"], bool]:
    """Initialise QgsApplication if needed. Returns (app, created_flag)."""
    if not HAS_QGIS:
        return None, False

    app = QgsApplication.instance()
    created = False
    if app is None:
        app = QgsApplication([], False)
        created = True

    already_init = bool(getattr(QgsApplication, "_CMD_INIT_DONE", False))
    if not already_init:
        prefix = _detect_qgis_prefix()
        if not prefix:
            raise RuntimeError("QGIS prefix path not found; set QGIS_PREFIX_PATH.")
        QgsApplication.setPrefixPath(prefix, True)
        QgsApplication.initQgis()
        QgsApplication._CMD_INIT_DONE = True

    return app, created


@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping integration test")
class QgisExportIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = _init_qgis_app()
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
