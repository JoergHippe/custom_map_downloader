"""Real-QGIS regression tests for the extent dialog's public behavior.

These exercise the actual Qt Designer form and QgsExtentGroupBox on QGIS 3/4.
Offscreen tests cannot prove interactive mouse drawing in a visible QGIS window.
"""

import os
import unittest

from tests.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRectangle,
    )
    from qgis.gui import QgsMapCanvas, QgsMapToolPan
    from qgis.PyQt.QtCore import QCoreApplication, QPoint, Qt
    from qgis.PyQt.QtTest import QTest
    from qgis.PyQt.QtWidgets import QWidget

    ensure_plugin_import_path()
    from custom_map_downloader.CustomMapDownloader_dialog import CustomMapDownloaderDialog

    HAS_QGIS = True
except Exception:
    if os.environ.get("CMD_REQUIRE_QGIS") == "1":
        raise
    HAS_QGIS = False


class _Interface:
    """Small real-widget substitute for the two QGIS iface methods used."""

    def __init__(self, parent, canvas):
        self._parent = parent
        self._canvas = canvas

    def mainWindow(self):
        return self._parent

    def mapCanvas(self):
        return self._canvas


@unittest.skipUnless(HAS_QGIS, "real QGIS/Qt bindings required")
class ExtentDialogIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.app_created = init_qgis_app()
        cls.project = QgsProject.instance()
        cls.prior_crs = cls.project.crs()
        cls.crs = QgsCoordinateReferenceSystem("EPSG:3857")
        cls.project.setCrs(cls.crs)

    @classmethod
    def tearDownClass(cls):
        cls.project.setCrs(cls.prior_crs)
        if cls.app_created and cls.app is not None:
            cls.app.exitQgis()

    def setUp(self):
        self.parent = QWidget()
        self.canvas = QgsMapCanvas(self.parent)
        self.canvas.resize(640, 400)
        self.canvas.setDestinationCrs(self.crs)
        self.canvas.setExtent(QgsRectangle(1000, 2000, 5000, 6000))
        self.iface = _Interface(self.parent, self.canvas)
        self.dialog = CustomMapDownloaderDialog(self.iface)
        self.addCleanup(self._close_dialog)
        QCoreApplication.processEvents()

    def _close_dialog(self):
        self.dialog._stop_extent_polling()
        self.dialog.close()
        self.dialog.deleteLater()
        self.canvas.deleteLater()
        self.parent.deleteLater()
        QCoreApplication.processEvents()

    def assert_rect(self, actual, expected):
        self.assertIsNotNone(actual)
        for method in ("xMinimum", "yMinimum", "xMaximum", "yMaximum"):
            self.assertAlmostEqual(getattr(actual, method)(), getattr(expected, method)(), places=4)

    def test_canvas_reset_replaces_user_extent(self):
        self.dialog.extentGroupBox.setOutputExtentFromUser(
            QgsRectangle(9000, 10000, 11000, 12000), self.crs
        )
        expected = QgsRectangle(self.canvas.extent())
        self.dialog.reset_extent_to_canvas()
        self.assert_rect(self.dialog._get_best_output_extent(commit=False), expected)

    def test_manually_selected_extent_is_used_for_profile(self):
        expected = QgsRectangle(1200, 2300, 4600, 5700)
        self.dialog.extentGroupBox.setOutputExtentFromUser(expected, self.crs)
        QCoreApplication.processEvents()
        self.assert_rect(self.dialog._get_best_output_extent(commit=False), expected)
        state = self.dialog._collect_profile_state()
        self.assertEqual(
            state["extent"],
            {"west": 1200.0, "south": 2300.0, "east": 4600.0, "north": 5700.0},
        )

    def test_draw_on_canvas_changes_selected_extent(self):
        """Exercise the real QGIS map tool with synthetic GUI mouse events."""
        self.parent.show()
        self.canvas.show()
        self.dialog.show()
        QCoreApplication.processEvents()

        previous = QgsRectangle(self.dialog.extentGroupBox.outputExtent())
        self.dialog.extentGroupBox.setOutputExtentFromDrawOnCanvas()
        QCoreApplication.processEvents()

        # QGIS installs its own QgsMapToolExtent on the canvas. Send Qt
        # mouse input to the canvas viewport, not directly to a fake signal.
        viewport = self.canvas.viewport()
        start = QPoint(100, 90)
        end = QPoint(350, 245)
        QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(viewport, pos=end, delay=10)
        QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
        QCoreApplication.processEvents()

        actual = self.dialog._get_best_output_extent(commit=False)
        self.assertIsNotNone(actual)
        self.assertNotEqual(
            self.dialog._extent_signature(actual, self.crs),
            self.dialog._extent_signature(previous, self.crs),
            "Drawing on the map must replace the previously selected extent.",
        )
        self.assertTrue(self.dialog.isVisible())

    def test_output_crs_change_transforms_selected_extent(self):
        original = QgsRectangle(1200, 2300, 4600, 5700)
        self.dialog.extentGroupBox.setOutputExtentFromUser(original, self.crs)

        geographic = QgsCoordinateReferenceSystem("EPSG:4326")
        expected = QgsCoordinateTransform(self.crs, geographic, self.project).transformBoundingBox(
            original
        )
        self.dialog.mQgsProjectionSelectionWidget.setCrs(geographic)
        QCoreApplication.processEvents()

        self.assertEqual(self.dialog.extentGroupBox.outputCrs().authid(), "EPSG:4326")
        self.assert_rect(self.dialog._get_best_output_extent(commit=False), expected)

    def test_repeated_canvas_drawing_updates_extent_each_time(self):
        self.parent.show()
        self.canvas.show()
        self.dialog.show()
        QCoreApplication.processEvents()

        previous = self.dialog._extent_signature(
            self.dialog._get_best_output_extent(commit=False), self.crs
        )
        viewport = self.canvas.viewport()
        for start, end in (
            (QPoint(100, 90), QPoint(350, 245)),
            (QPoint(190, 130), QPoint(280, 185)),
        ):
            self.dialog.extentGroupBox.setOutputExtentFromDrawOnCanvas()
            QCoreApplication.processEvents()
            QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
            QTest.mouseMove(viewport, pos=end, delay=10)
            QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
            QCoreApplication.processEvents()

            actual = self.dialog._get_best_output_extent(commit=False)
            signature = self.dialog._extent_signature(actual, self.crs)
            self.assertIsNotNone(signature)
            self.assertNotEqual(signature, previous)
            self.assertTrue(self.dialog.isVisible())
            previous = signature

    def test_abandon_canvas_drawing_keeps_previous_extent(self):
        """Deactivating the draw tool without dragging cancels the selection."""
        expected = QgsRectangle(1200, 2300, 4600, 5700)
        self.dialog.extentGroupBox.setOutputExtentFromUser(expected, self.crs)
        self.parent.show()
        self.canvas.show()
        self.dialog.show()
        QCoreApplication.processEvents()

        self.dialog.extentGroupBox.setOutputExtentFromDrawOnCanvas()
        QCoreApplication.processEvents()
        self.assertFalse(self.dialog.isVisible())

        # Switching tools deactivates QgsMapToolExtent without drawing.
        pan_tool = QgsMapToolPan(self.canvas)
        self.canvas.setMapTool(pan_tool)
        QCoreApplication.processEvents()

        self.assertTrue(self.dialog.isVisible())
        self.assert_rect(self.dialog._get_best_output_extent(commit=False), expected)
        self.canvas.unsetMapTool(pan_tool)

    def test_profile_restoration_uses_saved_extent(self):
        expected = QgsRectangle(1400, 2400, 4300, 5400)
        state = self.dialog._collect_profile_state()
        state["output_crs_authid"] = self.crs.authid()
        state["extent"] = {
            "west": expected.xMinimum(),
            "south": expected.yMinimum(),
            "east": expected.xMaximum(),
            "north": expected.yMaximum(),
        }
        self.assertFalse(self.dialog._apply_profile_state(state))
        self.assert_rect(self.dialog._get_best_output_extent(commit=False), expected)


if __name__ == "__main__":
    unittest.main()
