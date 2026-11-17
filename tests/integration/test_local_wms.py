"""Deterministic local WMS end-to-end checks with real QGIS rendering.

Only loopback HTTP is used; no external WMS provider, credentials, or internet
availability influence the test. A real QGIS WMS raster provider fetches
GetCapabilities and GetMap from an in-process HTTP server.
"""

import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tests.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app

try:
    from osgeo import gdal
    from qgis.core import QgsCoordinateReferenceSystem, QgsProject, QgsRasterLayer
    from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice
    from qgis.PyQt.QtGui import QColor, QImage

    ensure_plugin_import_path()
    from custom_map_downloader.core.exporter import GeoTiffExporter
    from custom_map_downloader.core.models import CenterSpec, ExportParams, ExtentSpec

    HAS_QGIS = True
except Exception:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_QGIS = False


def _png_bytes():
    """Encode a solid image using the QGIS-hosted Qt backend."""
    image = QImage(64, 64, QImage.Format.Format_RGBA8888)
    image.fill(QColor(24, 108, 198))
    data = QByteArray()
    buffer = QBuffer(data)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Unable to open PNG image buffer")
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Unable to create PNG test image")
    buffer.close()
    return bytes(data)


def _capabilities(url):
    """Minimal valid WMS 1.3.0 Capabilities including layer and service metadata."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0"
 xmlns="http://www.opengis.net/wms" xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.opengis.net/wms https://schemas.opengis.net/wms/1.3.0/capabilities_1_3_0.xsd">
 <Service>
  <Name>WMS</Name><Title>Local WMS Integration Test</Title>
  <OnlineResource xlink:type="simple" xlink:href="{url}"/>
 </Service>
 <Capability>
  <Request>
   <GetCapabilities><Format>text/xml</Format>
    <DCPType><HTTP><Get><OnlineResource xlink:type="simple" xlink:href="{url}"/></Get></HTTP></DCPType>
   </GetCapabilities>
   <GetMap><Format>image/png</Format>
    <DCPType><HTTP><Get><OnlineResource xlink:type="simple" xlink:href="{url}"/></Get></HTTP></DCPType>
   </GetMap>
  </Request>
  <Layer>
   <Title>Local layers</Title>
   <CRS>EPSG:3857</CRS>
   <EX_GeographicBoundingBox>
    <westBoundLongitude>-1</westBoundLongitude><eastBoundLongitude>1</eastBoundLongitude>
    <southBoundLatitude>-1</southBoundLatitude><northBoundLatitude>1</northBoundLatitude>
   </EX_GeographicBoundingBox>
   <Layer queryable="0" opaque="1">
    <Name>local_test</Name><Title>Solid test tile</Title>
    <CRS>EPSG:3857</CRS>
    <BoundingBox CRS="EPSG:3857" minx="-10000" miny="-10000" maxx="10000" maxy="10000"/>
    <Style><Name>default</Name><Title>Default</Title></Style>
   </Layer>
  </Layer>
 </Capability>
</WMS_Capabilities>""".encode("utf-8")


class _WmsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        server = self.server
        params = parse_qs(urlsplit(self.path).query)
        request = params.get("REQUEST", params.get("request", [""]))[0].lower()
        if request == "getcapabilities":
            server.capabilities_count += 1
            body = _capabilities(server.service_url)
            mime = "text/xml"
        elif request == "getmap":
            server.getmap_count += 1
            server.getmap_queries.append(params)
            body = server.image_bytes
            mime = "image/png"
        else:
            self.send_error(400, "Unsupported WMS request")
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        # Keep CI logs focused on assertions, not HTTP access records.
        return


@unittest.skipUnless(HAS_QGIS, "real QGIS bindings required")
class LocalWmsExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()
        cls.project = QgsProject.instance()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _WmsHandler)
        cls.server.service_url = (
            f"http://127.0.0.1:{cls.server.server_address[1]}/wms"
        )
        cls.server.capabilities_count = 0
        cls.server.getmap_count = 0
        cls.server.getmap_queries = []
        cls.server.image_bytes = _png_bytes()
        cls.server_thread = threading.Thread(
            target=cls.server.serve_forever, name="local-wms", daemon=True
        )
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)
        cls.project.removeAllMapLayers()
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def test_wms_export_uses_local_getmap_and_contains_pixels(self):
        uri = (
            f"url={self.server.service_url}&layers=local_test&styles=default"
            "&format=image/png&crs=EPSG:3857"
        )
        layer = QgsRasterLayer(uri, "Local WMS", "wms")
        self.assertTrue(layer.isValid(), f"WMS provider: {layer.error().summary()}")
        self.project.addMapLayer(layer)
        self.addCleanup(self.project.removeMapLayer, layer.id())
        crs = QgsCoordinateReferenceSystem("EPSG:3857")

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "local_wms.tif"
            extent = ExtentSpec(
                west=-4000, south=-4000, east=4000, north=4000, crs=crs
            )
            params = ExportParams(
                layer=layer,
                width_px=128,
                height_px=128,
                gsd_m_per_px=62.5,
                center=CenterSpec(northing=0, easting=0, crs=crs),
                extent=extent,
                output_path=str(output),
                load_as_layer=False,
                render_crs=crs,
                output_crs=crs,
            )
            result = GeoTiffExporter().export(params)
            self.assertEqual(result, str(output))
            dataset = gdal.Open(str(output))
            self.assertIsNotNone(dataset)
            self.assertEqual((dataset.RasterXSize, dataset.RasterYSize), (128, 128))
            rgb = dataset.ReadAsArray()
            self.assertIsNotNone(rgb)
            self.assertGreater(int(rgb[0].max()), 0)
            dataset = None

        self.assertGreaterEqual(self.server.capabilities_count, 1)
        self.assertGreaterEqual(self.server.getmap_count, 1)
        requested = self.server.getmap_queries[-1]
        self.assertIn("BBOX", requested)
        self.assertEqual(requested["LAYERS"][0], "local_test")


if __name__ == "__main__":
    unittest.main()
