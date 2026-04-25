import logging
import unittest

from tests.test_exporter_validation import install_qgis_stubs

install_qgis_stubs()

from qgis.core import QgsCoordinateReferenceSystem  # noqa: E402

from custom_map_downloader.core.export_logging import (  # noqa: E402
    LOGGER,
    log_event,
    summarize_params,
)
from custom_map_downloader.core.models import CenterSpec, ExportParams  # noqa: E402


class ExportLoggingTests(unittest.TestCase):
    def _params(self):
        crs = QgsCoordinateReferenceSystem("EPSG:3857")
        return ExportParams(
            layer=object(),
            width_px=512,
            height_px=256,
            gsd_m_per_px=1.0,
            center=CenterSpec(northing=2.0, easting=1.0, crs=crs),
            extent=None,
            output_path="/tmp/out.tif",
            load_as_layer=False,
            render_crs=crs,
            output_crs=crs,
        )

    def test_summarize_params_contains_core_fields(self):
        params = self._params()
        summary = summarize_params(
            params, render_crs=params.render_crs, output_crs=params.output_crs
        )
        self.assertEqual(summary["render_crs"], "EPSG:3857")
        self.assertEqual(summary["output_crs"], "EPSG:3857")
        self.assertEqual(summary["width_px"], 512)
        self.assertFalse(summary["create_vrt"])

    def test_log_event_emits_structured_line(self):
        with self.assertLogs(LOGGER, level=logging.INFO) as captured:
            log_event("export_start", output_path="/tmp/out.tif", width_px=512)
        self.assertIn("export_start", captured.output[0])
        self.assertIn("output_path='/tmp/out.tif'", captured.output[0])
        self.assertIn("width_px=512", captured.output[0])


if __name__ == "__main__":
    unittest.main()
