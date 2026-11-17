"""Offline WMTS KVP/REST end-to-end test through the real QGIS raster provider.

Serves WMTS 1.0.0 GetCapabilities and PNG GetTile responses on 127.0.0.1.
No internet or external map-service credentials are required.
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

    ensure_plugin_import_path()
    from custom_map_downloader.core.exporter import GeoTiffExporter
    from custom_map_downloader.core.models import CenterSpec, ExportParams, ExtentSpec
    from tests.integration.test_local_wms import _png_bytes

    HAS_QGIS = True
except Exception:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_QGIS = False


def _wmts_capabilities(url):
    matrices = []
    for zoom in range(3):
        matrix_size = 1 << zoom
        scale = 559082264.0287178 / matrix_size
        matrices.append(
            f"""<TileMatrix><ows:Identifier>{zoom}</ows:Identifier>
             <ScaleDenominator>{scale}</ScaleDenominator>
             <TopLeftCorner>-20037508.342789244 20037508.342789244</TopLeftCorner>
             <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
             <MatrixWidth>{matrix_size}</MatrixWidth><MatrixHeight>{matrix_size}</MatrixHeight>
             </TileMatrix>"""
        )
    matrix_xml = "".join(matrices)
    # The REST URL tests QGIS's actual WMTS tile path, not an XYZ shortcut.
    tile_url = url + "/local_wmts/default/local_mercator/" "{TileMatrix}/{TileRow}/{TileCol}.png"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0"
 xmlns:ows="http://www.opengis.net/ows/1.1"
 xmlns:xlink="http://www.w3.org/1999/xlink" version="1.0.0">
 <ows:ServiceIdentification>
  <ows:Title>Local WMTS Integration Test</ows:Title>
  <ows:ServiceType>OGC WMTS</ows:ServiceType>
  <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
 </ows:ServiceIdentification>
 <ows:OperationsMetadata>
  <ows:Operation name="GetCapabilities">
   <ows:DCP><ows:HTTP><ows:Get xlink:href="{url}">
    <ows:Constraint name="GetEncoding"><ows:AllowedValues>
     <ows:Value>KVP</ows:Value>
    </ows:AllowedValues></ows:Constraint>
   </ows:Get></ows:HTTP></ows:DCP>
  </ows:Operation>
  <ows:Operation name="GetTile">
   <ows:DCP><ows:HTTP><ows:Get xlink:href="{url}">
    <ows:Constraint name="GetEncoding"><ows:AllowedValues>
     <ows:Value>KVP</ows:Value>
    </ows:AllowedValues></ows:Constraint>
   </ows:Get></ows:HTTP></ows:DCP>
  </ows:Operation>
 </ows:OperationsMetadata>
 <Contents>
  <Layer>
   <ows:Title>Local WMTS test tiles</ows:Title>
   <ows:Identifier>local_wmts</ows:Identifier>
   <ows:WGS84BoundingBox>
    <ows:LowerCorner>-180 -85</ows:LowerCorner>
    <ows:UpperCorner>180 85</ows:UpperCorner>
   </ows:WGS84BoundingBox>
   <Style isDefault="true"><ows:Identifier>default</ows:Identifier></Style>
   <Format>image/png</Format>
   <TileMatrixSetLink><TileMatrixSet>local_mercator</TileMatrixSet></TileMatrixSetLink>
   <ResourceURL format="image/png" resourceType="tile" template="{tile_url}"/>
  </Layer>
  <TileMatrixSet>
   <ows:Identifier>local_mercator</ows:Identifier>
   <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
   {matrix_xml}
  </TileMatrixSet>
 </Contents>
</Capabilities>""".encode(
        "utf-8"
    )


class _WmtsHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib server interface
        server = self.server
        path = urlsplit(self.path)
        params = {key.lower(): val for key, val in parse_qs(path.query).items()}
        request = params.get("request", [""])[0].lower()

        if request == "gettile" or path.path.endswith(".png"):
            server.gettile_count += 1
            body = server.image_bytes
            mime = "image/png"
        elif request == "getcapabilities" or path.path == "/wmts":
            server.capabilities_count += 1
            body = _wmts_capabilities(server.service_url)
            mime = "text/xml"
        else:
            self.send_error(400, "Unsupported WMTS request")
            return

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format, *_args):
        return


@unittest.skipUnless(HAS_QGIS, "real QGIS bindings required")
class LocalWmtsExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()
        cls.project = QgsProject.instance()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _WmtsHandler)
        cls.server.service_url = f"http://127.0.0.1:{cls.server.server_address[1]}/wmts"
        cls.server.capabilities_count = 0
        cls.server.gettile_count = 0
        cls.server.image_bytes = _png_bytes()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.project.removeAllMapLayers()
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def test_wmts_getcapabilities_and_tile_export(self):
        uri = (
            f"url={self.server.service_url}&layers=local_wmts&styles=default"
            "&format=image/png&crs=EPSG:3857&tileMatrixSet=local_mercator"
        )
        layer = QgsRasterLayer(uri, "Local WMTS", "wms")
        self.assertTrue(layer.isValid(), f"WMTS provider: {layer.error().summary()}")
        self.project.addMapLayer(layer)
        self.addCleanup(self.project.removeMapLayer, layer.id())
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "local_wmts.tif"
            params = ExportParams(
                layer=layer,
                width_px=128,
                height_px=128,
                gsd_m_per_px=62.5,
                center=CenterSpec(northing=0, easting=0, crs=crs),
                extent=ExtentSpec(west=-4000, south=-4000, east=4000, north=4000, crs=crs),
                output_path=str(output),
                load_as_layer=False,
                render_crs=crs,
                output_crs=crs,
            )
            self.assertEqual(GeoTiffExporter().export(params), str(output))
            data = gdal.Open(str(output))
            self.assertIsNotNone(data)
            self.assertEqual((data.RasterXSize, data.RasterYSize), (128, 128))
            self.assertGreater(int(data.ReadAsArray()[0].max()), 0)
            data = None

        self.assertGreater(self.server.capabilities_count, 0)
        self.assertGreater(self.server.gettile_count, 0)


if __name__ == "__main__":
    unittest.main()
