import json
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "test" / "integration" / "config.json"

warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo.gdal")
warnings.filterwarnings("ignore", category=FutureWarning, module="osgeo")

def _detect_qgis_prefix() -> str:
    prefix_env = os.environ.get("QGIS_PREFIX_PATH", "").strip()
    candidates = [
        prefix_env,
        r"C:\OSGeo4W64\apps\qgis",
        r"C:\OSGeo4W\apps\qgis",
        r"C:\Program Files\QGIS 3.36.0\apps\qgis",
        r"C:\Program Files\QGIS 3.34.0\apps\qgis",
    ]
    return next((p for p in candidates if p and Path(p).exists()), "")


if TYPE_CHECKING:
    from qgis.core import (
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
        QgsRectangle,
    )
else:
    QgsApplication = object  # type: ignore
    QgsCoordinateReferenceSystem = object  # type: ignore
    QgsProject = object  # type: ignore
    QgsRasterLayer = object  # type: ignore
    QgsRectangle = object  # type: ignore

try:
    from qgis.core import (  # type: ignore
        QgsApplication,
        QgsCoordinateReferenceSystem,
        QgsProject,
        QgsRasterLayer,
        QgsRectangle,
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


def _load_config():
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _env_override_extent() -> dict:
    """Allow extent override via ENV: EXTENT_W/E/S/N (float)."""
    keys = ["WEST", "EAST", "SOUTH", "NORTH"]
    vals = {}
    for k in keys:
        env_val = os.environ.get(f"EXTENT_{k}", "").strip()
        if env_val:
            try:
                vals[k.lower()] = float(env_val)
            except ValueError:
                pass
    return vals


def _http_status_from_uri(uri: str) -> Optional[int]:
    """Quick HEAD/GET check to see if the WMS base is reachable."""
    try:
        # Extract base URL after url=... and strip params to the first '?'
        if uri.startswith("url="):
            raw = uri[4:]
        else:
            raw = uri
        parts = raw.split("url=", 1)
        base = parts[1] if len(parts) > 1 else raw
        base = base.split("&", 1)[0]
        # Falls kein Schema vorhanden ist, nicht versuchen.
        if not base.lower().startswith(("http://", "https://")):
            return None

        req = urlopen(base, timeout=10)  # nosec - nur Testdiagnostik
        return getattr(req, "status", None) or getattr(req, "code", None)
    except Exception:
        return None


@unittest.skipUnless(HAS_QGIS, "QGIS not available; skipping integration test")
class QgisNetworkIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _load_config()
        if cls.config is None:
            raise unittest.SkipTest("No config.json found for network tests")
        cls.sources = {s["name"]: s for s in cls.config.get("sources", []) if "name" in s}
        cls.defaults = cls.config.get("defaults", {})
        raw_filter = os.environ.get("SCENARIOS", "")
        cls.scenario_filter = {name.strip() for name in raw_filter.split(",") if name.strip()}

        allow_net = os.environ.get("ALLOW_INTEGRATION_NETWORK", "").lower() in {"1", "true", "yes"}
        if not allow_net:
            raise unittest.SkipTest("Network tests disabled (set ALLOW_INTEGRATION_NETWORK=1 to enable)")

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

    def test_network_scenarios(self):
        scenarios = self.config.get("scenarios", [])
        tmpdir = Path(tempfile.gettempdir())
        env_crs = os.environ.get("CRS", "").strip()
        env_extent = _env_override_extent()
        ok_count = 0
        skip_count = 0
        fail_messages: list[str] = []

        print("[INFO] Starte Netz-Szenarien...")

        for scenario in scenarios:
            name = scenario.get("name", "unnamed")
            if self.scenario_filter and name not in self.scenario_filter:
                continue

            source_name = scenario.get("source")
            source = self.sources.get(source_name or "", {}) or {}
            provider = scenario.get("provider") or source.get("provider", "wms")
            uri = scenario.get("uri") or source.get("uri", "")
            crs_authid = env_crs or scenario.get("crs") or source.get("default_crs") or self.defaults.get("crs", "EPSG:3857")
            ext_cfg = scenario.get("extent", {}) or source.get("extent", {}) or self.defaults.get("extent", {})
            if env_extent:
                ext_cfg = {**ext_cfg, **env_extent}
            gsd = float(scenario.get("gsd", source.get("gsd", self.defaults.get("gsd", 1.0))))
            create_vrt = bool(scenario.get("create_vrt", source.get("create_vrt", self.defaults.get("create_vrt", False))))
            vrt_size = int(scenario.get("vrt_preset_size", source.get("vrt_preset_size", self.defaults.get("vrt_preset_size", 0))))
            out_ext = scenario.get("output_extension", source.get("output_extension", self.defaults.get("output_extension", ".tif")))

            crs = QgsCoordinateReferenceSystem(crs_authid)
            if not crs.isValid():
                msg = f"[SKIP] {name}: Invalid CRS {crs_authid}"
                print(msg)
                skip_count += 1
                continue

            status = _http_status_from_uri(uri)

            layer = QgsRasterLayer(uri, name, provider)
            if not layer.isValid():
                # Detailierte Fehlermeldung für schnellere Diagnose
                layer_err = ""
                try:
                    err_obj = layer.error()
                    if err_obj:
                        layer_err = getattr(err_obj, "summary", lambda: str(err_obj))()
                except Exception:
                    pass

                if status and status != 200:
                    print(f"[SKIP] {name}: WMS base unreachable (HTTP {status}) uri={uri}")
                else:
                    print(f"[SKIP] {name}: Layer invalid; provider={provider}; uri={uri}; error={layer_err}")
                skip_count += 1
                continue

            self.project.addMapLayer(layer)

            if ext_cfg:
                rect = QgsRectangle(
                    float(ext_cfg["west"]),
                    float(ext_cfg["south"]),
                    float(ext_cfg["east"]),
                    float(ext_cfg["north"]),
                )
            else:
                rect = layer.extent()

            center = rect.center()
            width_px = max(1, int(round(rect.width() / gsd)))
            height_px = max(1, int(round(rect.height() / gsd)))

            out_path = tmpdir / f"cmd_net_{name}{out_ext}"
            if out_path.exists():
                out_path.unlink()

            params = ExportParams(
                layer=layer,
                width_px=width_px,
                height_px=height_px,
                gsd_m_per_px=gsd,
                center=CenterSpec(northing=center.y(), easting=center.x(), crs=crs),
                extent=ExtentSpec(
                    west=rect.xMinimum(),
                    south=rect.yMinimum(),
                    east=rect.xMaximum(),
                    north=rect.yMaximum(),
                    crs=crs,
                ),
                output_path=str(out_path),
                load_as_layer=False,
                render_crs=crs,
                output_crs=crs,
                create_vrt=create_vrt,
                vrt_max_cols=vrt_size,
                vrt_max_rows=vrt_size,
                vrt_preset_size=vrt_size,
            )

            try:
                exporter = GeoTiffExporter()
                result_path = exporter.export(params)
                if not Path(result_path).exists():
                    raise RuntimeError("Export fehlgeschlagen, Datei fehlt.")
                print(f"[OK]   {name}")
                ok_count += 1
            except Exception as ex:
                msg = f"[ERROR] {name}: {ex}"
                print(msg)
                fail_messages.append(msg)
            finally:
                # Cleanup layer/file
                try:
                    self.project.removeMapLayer(layer.id())
                except Exception:
                    pass
                if out_path.exists():
                    out_path.unlink()

        print(f"[INFO] Summary: OK={ok_count}, SKIP={skip_count}, FAIL={len(fail_messages)}")
        if fail_messages:
            self.fail("\n".join(fail_messages))


if __name__ == "__main__":
    unittest.main()
