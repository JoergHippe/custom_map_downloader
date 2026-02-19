import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple


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
    candidates = [
        prefix_env,
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

    from core.exporter import GeoTiffExporter  # type: ignore
    from core.models import ExportParams, CenterSpec, ExtentSpec  # type: ignore

    HAS_QGIS = True
except Exception:
    HAS_QGIS = False
else:
    # Unterdrückt das bekannte GDAL FutureWarning-Rauschen im Test-Output.
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
        setattr(QgsApplication, "_CMD_INIT_DONE", True)

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

    def test_export_small_raster(self):
        if not TEST_DATA.exists():
            self.skipTest("Test raster not found")

        layer = QgsRasterLayer(str(TEST_DATA), "test_raster")
        self.assertTrue(layer.isValid(), "Raster layer failed to load")

        # Force a projected CRS (meters) to satisfy exporter requirements.
        metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        layer.setCrs(metric_crs)

        self.project.addMapLayer(layer)

        extent = layer.extent()
        center = extent.center()

        output_path = Path(tempfile.gettempdir()) / "cmd_integration_export.tif"
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
            output_crs=metric_crs,
            create_vrt=False,
            vrt_max_cols=0,
            vrt_max_rows=0,
            vrt_preset_size=0,
        )

        exporter = GeoTiffExporter()
        result_path = exporter.export(params)
        self.assertTrue(Path(result_path).exists(), "Exported file not found")

        # Cleanup
        try:
            self.project.removeMapLayer(layer.id())
        except Exception:
            pass
        if output_path.exists():
            output_path.unlink()


if __name__ == "__main__":
    unittest.main()
