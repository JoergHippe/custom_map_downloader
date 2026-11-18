"""Real-QGIS regression tests for the extent dialog's public behavior.

These exercise the actual Qt Designer form and QgsExtentGroupBox on QGIS 3/4.
Offscreen tests cannot prove interactive mouse drawing in a visible QGIS window.
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.integration.qgis_test_support import ensure_plugin_import_path, init_qgis_app

try:
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRectangle,
        QgsVectorLayer,
    )
    from qgis.gui import QgsMapCanvas, QgsMapToolPan
    from qgis.PyQt.QtCore import QCoreApplication, QPoint, Qt
    from qgis.PyQt.QtTest import QTest
    from qgis.PyQt.QtWidgets import QWidget

    ensure_plugin_import_path()
    from custom_map_downloader.core.scale import gsd_to_scale_denominator, scale_to_gsd_m_per_px
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
        # The dialog persists CRS choices across instances. Each test must
        # establish its own metric baseline, independent of execution order.
        self.dialog.mQgsProjectionSelectionWidget.setCrs(self.crs)
        self.dialog.reset_extent_to_canvas()
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

    def test_last_layer_setting_restored_and_refresh_keeps_new_selection(self):
        """QSettings startup order and refresh must not reset the selected layer."""
        # Keep Qt layer-combo behavior real, but avoid deleting native QGIS
        # layers while QgsExtentGroupBox may still hold C++ references.
        first = SimpleNamespace(id=lambda: "first-id", name=lambda: "first")
        second = SimpleNamespace(id=lambda: "second-id", name=lambda: "second")
        project = SimpleNamespace(
            mapLayers=lambda: {"first-id": first, "second-id": second},
            crs=self.project.crs,
        )

        with patch.object(CustomMapDownloaderDialog, "_project", return_value=project):
            self.dialog.populate_layers()

            def stored_value(key, default="", type=None):
                return second.id() if key.endswith("last_layer_id") else default

            with patch("custom_map_downloader.CustomMapDownloader_dialog.QSettings") as settings:
                settings.return_value.value.side_effect = stored_value
                self.dialog._load_settings()

            self.assertEqual(self.dialog.comboBox_layer.currentData().id(), second.id())

            # A manual layer change must take precedence over stale settings.
            first_index = next(
                i
                for i in range(self.dialog.comboBox_layer.count())
                if self.dialog.comboBox_layer.itemData(i).id() == first.id()
            )
            self.dialog.comboBox_layer.setCurrentIndex(first_index)
            self.assertEqual(self.dialog._last_layer_id, first.id())
            self.dialog.populate_layers()
            self.assertEqual(self.dialog.comboBox_layer.currentData().id(), first.id())

    def test_profile_restores_vrt_when_previous_format_was_mbtiles(self):
        """Qt signal ordering must not silently rewrite a VRT profile to MBTiles."""
        self.dialog._restore_output_path(str(Path(tempfile.gettempdir()) / "previous.mbtiles"))
        self.assertEqual(self.dialog._selected_output_extension(), ".mbtiles")
        profile = self.dialog._collect_profile_state()
        expected = str(Path(tempfile.gettempdir()) / "restored.vrt")
        profile.update({"output_path": expected, "create_vrt": True, "extent": None})

        self.dialog._apply_profile_state(profile)

        self.assertEqual(self.dialog.lineEdit_outputDirectory.text(), expected)
        self.assertTrue(self.dialog.checkBox_createVrt.isChecked())
        self.assertEqual(self.dialog._selected_output_extension(), ".tif")

    def test_last_output_setting_restores_vrt_checkbox(self):
        """A saved .vrt path must restore the actual VRT control state."""
        expected = str(Path(tempfile.gettempdir()) / "last_output.vrt")

        def stored_value(key, default="", type=None):
            return expected if key.endswith("last_output_path") else default

        with patch("custom_map_downloader.CustomMapDownloader_dialog.QSettings") as settings:
            settings.return_value.value.side_effect = stored_value
            self.dialog._load_settings()

        self.assertEqual(self.dialog.lineEdit_outputDirectory.text(), expected)
        self.assertTrue(self.dialog.checkBox_createVrt.isChecked())
        self.assertEqual(self.dialog._selected_output_extension(), ".tif")

    def test_resolution_changes_refresh_previews_once(self):
        """Synchronizing the paired spinboxes must not double-refresh output."""
        self.dialog.comboBox_resolutionMode.setCurrentIndex(
            self.dialog.comboBox_resolutionMode.findData("gsd")
        )
        with patch.object(self.dialog, "_refresh_resolution_previews") as refresh:
            self.dialog.spinBox_gsd.setValue(3.5)
            self.assertEqual(refresh.call_count, 1)
        self.assertAlmostEqual(
            self.dialog.doubleSpinBox_targetScale.value(),
            round(gsd_to_scale_denominator(3.5)),
            delta=1,
        )

        self.dialog.comboBox_resolutionMode.setCurrentIndex(
            self.dialog.comboBox_resolutionMode.findData("scale")
        )
        with patch.object(self.dialog, "_refresh_resolution_previews") as refresh:
            self.dialog.doubleSpinBox_targetScale.setValue(50000)
            self.assertEqual(refresh.call_count, 1)
        self.assertAlmostEqual(
            self.dialog.spinBox_gsd.value(),
            scale_to_gsd_m_per_px(50000),
            places=3,
        )

    def test_vrt_preset_updates_tile_grid_once(self):
        """Qt signal blocking avoids intermediate VRT previews for each spinbox."""
        self.dialog.checkBox_createVrt.setChecked(True)
        preset = self.dialog.comboBox_vrtPreset
        next_index = 0 if preset.currentIndex() != 0 else 1
        expected = int(preset.itemText(next_index))

        with patch.object(
            self.dialog, "_update_vrt_info", wraps=self.dialog._update_vrt_info
        ) as update:
            preset.setCurrentIndex(next_index)
            self.assertEqual(update.call_count, 1)

        self.assertEqual(self.dialog.spinBox_vrtMaxCols.value(), expected)
        self.assertEqual(self.dialog.spinBox_vrtMaxRows.value(), expected)

    def test_resolution_change_does_not_recompute_mbtiles_coverage(self):
        """MBTiles tile counts depend on extent and zoom, not GSD or scale."""
        self.dialog.comboBox_resolutionMode.setCurrentIndex(
            self.dialog.comboBox_resolutionMode.findData("gsd")
        )
        with patch.object(self.dialog, "_update_mbtiles_info") as update:
            self.dialog.spinBox_gsd.setValue(3.7)
            update.assert_not_called()

    def test_profile_resolution_mode_wins_over_conflicting_inactive_value(self):
        """Restoring a profile must honor the selected input, not signal order."""
        profile = self.dialog._collect_profile_state()
        profile.update(
            {
                "resolution_mode": "gsd",
                "gsd": 5.5,
                "target_scale_denominator": 1000,
                "extent": None,
            }
        )
        self.dialog._apply_profile_state(profile)
        self.assertEqual(self.dialog._resolution_mode(), "gsd")
        self.assertAlmostEqual(self.dialog._current_gsd(), 5.5, places=3)
        self.assertAlmostEqual(
            self.dialog.doubleSpinBox_targetScale.value(),
            round(gsd_to_scale_denominator(5.5)),
            delta=1,
        )

        profile.update(
            {
                "resolution_mode": "scale",
                "gsd": 0.5,
                "target_scale_denominator": 50000,
            }
        )
        self.dialog._apply_profile_state(profile)
        self.assertEqual(self.dialog._resolution_mode(), "scale")
        self.assertAlmostEqual(self.dialog._current_target_scale(), 50000)
        self.assertAlmostEqual(
            self.dialog.spinBox_gsd.value(),
            scale_to_gsd_m_per_px(50000),
            places=3,
        )

    def test_qsettings_resolution_mode_wins_over_stale_secondary_value(self):
        """Last used target scale must not override a GSD-driven saved session."""

        def stored_value(key, default="", type=None):
            values = {
                "last_resolution_mode": "gsd",
                "last_gsd": 4.5,
                "last_target_scale": 1000,
            }
            return values.get(key.split("/")[-1], default)

        with patch("custom_map_downloader.CustomMapDownloader_dialog.QSettings") as settings:
            settings.return_value.value.side_effect = stored_value
            self.dialog._load_settings()

        self.assertEqual(self.dialog._resolution_mode(), "gsd")
        self.assertAlmostEqual(self.dialog._current_gsd(), 4.5, places=3)
        self.assertAlmostEqual(
            self.dialog.doubleSpinBox_targetScale.value(),
            round(gsd_to_scale_denominator(4.5)),
            delta=1,
        )

    def test_internal_coordinate_mapping_does_not_alias_fields(self):
        """Document QGIS child-widget mapping without assuming private names."""
        self.dialog._cache_extent_line_edits()
        mapping = self.dialog._extent_line_edits
        details = {
            slot: (
                (
                    widget.objectName(),
                    widget.toolTip(),
                    widget.text(),
                )
                if widget is not None
                else None
            )
            for slot, widget in mapping.items()
        }
        print(f"Extent line-edit resolution: {details}")
        resolved = [widget for widget in mapping.values() if widget is not None]
        self.assertEqual(len(resolved), 4, details)
        self.assertEqual(
            len(set(id(widget) for widget in resolved)),
            len(resolved),
            "One private QGIS coordinate field was assigned to multiple axes.",
        )

    def test_editing_xmax_in_widget_updates_only_xmax(self):
        """QTest key input must update the selected extent, not a different axis."""
        initial = QgsRectangle(1200, 2300, 4600, 5700)
        self.dialog.extentGroupBox.setOutputExtentFromUser(initial, self.crs)
        self.dialog._cache_extent_line_edits()
        xedit = self.dialog._extent_line_edits["xmax"]
        self.assertIsNotNone(xedit)
        self.dialog.show()
        QCoreApplication.processEvents()

        xedit.setFocus()
        xedit.selectAll()
        QTest.keyClicks(xedit, "4900")
        QTest.keyPress(xedit, Qt.Key.Key_Tab)
        QCoreApplication.processEvents()

        actual = self.dialog.extentGroupBox.outputExtent()
        self.assertAlmostEqual(actual.xMaximum(), 4900.0, places=3)
        self.assertAlmostEqual(actual.yMaximum(), 5700.0, places=3)
        self.assertAlmostEqual(actual.xMinimum(), 1200.0, places=3)

    def test_fallback_parses_german_and_english_decimal_formats(self):
        """Fallback coordinates must not depend on the CI runner's locale."""
        cases = (
            ("1,25", 1.25),
            ("1.234,50", 1234.5),
            ("1,234.50", 1234.5),
            ("1234.50", 1234.5),
            ("-4,000.0000", -4000.0),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertAlmostEqual(self.dialog._try_parse_float(raw), expected, places=5)

    def test_reset_populates_visible_fields_via_public_qgis_api(self):
        """No direct setText on private editors should be needed for reset."""
        self.dialog.extentGroupBox.setOutputExtentFromUser(
            QgsRectangle(9000, 10000, 11000, 12000), self.crs
        )
        self.dialog.reset_extent_to_canvas()
        self.dialog._cache_extent_line_edits()
        rect = self.dialog.extentGroupBox.outputExtent()
        expected = {
            "xmin": rect.xMinimum(),
            "xmax": rect.xMaximum(),
            "ymin": rect.yMinimum(),
            "ymax": rect.yMaximum(),
        }
        for axis, value in expected.items():
            with self.subTest(axis=axis):
                edit = self.dialog._extent_line_edits[axis]
                self.assertIsNotNone(edit)
                self.assertAlmostEqual(self.dialog._try_parse_float(edit.text()), value, places=3)

    def test_unknown_private_field_names_are_not_guessed(self):
        """Never infer coordinate axes from order or translated UI labels."""
        rect = QgsRectangle(self.dialog.extentGroupBox.outputExtent())
        mapping = self.dialog._extent_line_edits
        widget = mapping["xmax"]
        self.assertIsNotNone(widget)
        original_name = widget.objectName()
        try:
            widget.setObjectName("unknown_coordinate_widget")
            self.dialog._cache_extent_line_edits()
            self.assertIsNone(self.dialog._extent_line_edits["xmax"])
            self.assert_rect(self.dialog._get_best_output_extent(commit=False), rect)
        finally:
            widget.setObjectName(original_name)
            self.dialog._cache_extent_line_edits()

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

    def test_metric_dimensions_fail_closed_when_transform_fails(self):
        """Never interpret a geographic extent as meters if reprojection fails."""
        geographic = QgsCoordinateReferenceSystem("EPSG:4326")
        self.dialog.mQgsProjectionSelectionWidget.setCrs(geographic)
        self.dialog.extentGroupBox.setOutputExtentFromUser(
            QgsRectangle(12.0, 51.0, 12.01, 51.01), geographic
        )
        with patch(
            "custom_map_downloader.CustomMapDownloader_dialog.QgsCoordinateTransform",
            side_effect=RuntimeError("simulated CRS transform failure"),
        ):
            width_m, height_m, valid = self.dialog._get_extent_in_meters()
        self.assertFalse(valid)
        self.assertEqual((width_m, height_m), (0.0, 0.0))

    def test_export_parameters_fail_closed_when_project_transform_fails(self):
        """A failed output-to-project transform must never relabel coordinates."""
        geographic = QgsCoordinateReferenceSystem("EPSG:4326")
        self.dialog.mQgsProjectionSelectionWidget.setCrs(geographic)
        self.dialog.extentGroupBox.setOutputExtentFromUser(
            QgsRectangle(12.0, 51.0, 12.01, 51.01), geographic
        )
        layer = QgsVectorLayer("Point?crs=EPSG:3857", "test layer", "memory")
        self.assertTrue(layer.isValid())
        self.dialog.comboBox_layer.addItem("test layer", layer)
        self.dialog.comboBox_layer.setCurrentIndex(self.dialog.comboBox_layer.count() - 1)

        with tempfile.TemporaryDirectory() as directory:
            self.dialog.lineEdit_outputDirectory.setText(str(Path(directory) / "output.tif"))
            with (
                patch.object(self.dialog, "_current_gsd", return_value=1.0),
                patch.object(self.dialog, "_compute_pixel_dimensions", return_value=(100, 100)),
                patch(
                    "custom_map_downloader.CustomMapDownloader_dialog.QgsCoordinateTransform",
                    side_effect=RuntimeError("simulated CRS transform failure"),
                ),
            ):
                self.assertIsNone(self.dialog.get_parameters())

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
