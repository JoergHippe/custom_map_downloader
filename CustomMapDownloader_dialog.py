# CustomMapDownloader/CustomMapDownloader_dialog.py
# -*- coding: utf-8 -*-
"""Dialog for CustomMapDownloader.

Semantics:
- Extent is fully handled by QgsExtentGroupBox (built-in QGIS logic).
- Resolution is controlled via a single GSD value (map units per pixel).
- Pixel dimensions are derived from extent and GSD.
- VRT section exposes tiling parameters including presets and a tile count preview.

Robustness patch for "Draw on canvas":
- QgsExtentGroupBox may update its visible min/max fields without committing a valid outputExtent().
- This dialog therefore resolves the "best available" extent in this order:
    1) extentGroupBox.outputExtent()
    2) extentGroupBox.currentExtent() (and tries to commit it)
    3) parse visible xmin/xmax/ymin/ymax QLineEdits (and tries to commit it)
- Additionally, a small timer polls for changes to keep the info labels updated even when
  extentChanged is not emitted for "Draw on canvas".
"""

from __future__ import annotations

import math
import os
from typing import Optional, Tuple, cast

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QTimer, Qt, QLocale, QCoreApplication, QSettings
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from .core.constants import (
    GSD_MIN,
    GSD_STEP,
    GSD_DECIMALS,
    GSD_MAX,
)
from .core.validation import pixel_limit_status
from qgis.gui import QgsExtentWidget

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "CustomMapDownloader_dialog_base.ui")
)
FORM_CLASS = cast(type, FORM_CLASS)


class CustomMapDownloaderDialog(QtWidgets.QDialog, FORM_CLASS):  # type: ignore[misc, valid-type]
    """Parameter dialog for the CustomMapDownloader plugin."""

    def __init__(self, iface, parent=None):
        """Initialize dialog and wire UI elements."""
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setupUi(self)

        self._apply_ui_constants()
        self._init_output_format_combo()
        self._apply_tooltips()

        self.setWindowModality(Qt.WindowModal)

        # Wire OK / Cancel of QDialogButtonBox
        if hasattr(self, "buttonBox"):
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.reject)

        self._extent_info_default = ""
        if hasattr(self, "label_extentInfo"):
            self._extent_info_default = self.label_extentInfo.text() or ""

        # Polling timer for "Draw on canvas" mode (extentChanged may not fire reliably)
        self._extent_poll_timer: Optional[QTimer] = None
        self._last_extent_signature: Optional[Tuple[float, float, float, float, str]] = None

        # ------------------------------------------------------------------
        # Wire basic UI
        # ------------------------------------------------------------------
        if hasattr(self, "pushButton_browse"):
            self.pushButton_browse.clicked.connect(self.select_output_directory)

        if hasattr(self, "pushButton_refreshLayers"):
            self.pushButton_refreshLayers.clicked.connect(self.populate_layers)

        if hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.valueChanged.connect(self._update_extent_info)
            self.spinBox_gsd.valueChanged.connect(self._update_vrt_info)

        if hasattr(self, "comboBox_layer"):
            self.comboBox_layer.currentIndexChanged.connect(self._on_layer_changed)

        if hasattr(self, "mQgsProjectionSelectionWidget"):
            self.mQgsProjectionSelectionWidget.crsChanged.connect(self._on_output_crs_changed)

        if hasattr(self, "extentGroupBox"):
            self.extentGroupBox.extentChanged.connect(self._on_extent_changed)

        # VRT tiling controls
        if hasattr(self, "checkBox_createVrt"):
            self.checkBox_createVrt.toggled.connect(self._on_create_vrt_toggled)
        if hasattr(self, "comboBox_vrtPreset"):
            self.comboBox_vrtPreset.currentIndexChanged.connect(self._on_vrt_preset_changed)
        if hasattr(self, "spinBox_vrtMaxCols"):
            self.spinBox_vrtMaxCols.valueChanged.connect(self._update_vrt_info)
        if hasattr(self, "spinBox_vrtMaxRows"):
            self.spinBox_vrtMaxRows.valueChanged.connect(self._update_vrt_info)

        # ------------------------------------------------------------------
        # Init
        # ------------------------------------------------------------------
        self.populate_layers()
        self._init_crs_widgets()
        self._init_extent_group_box()

        # Hide only the problematic "current layer extent" button,
        # keep the "from layer" button visible.
        self._hide_project_layer_extent_button()

        # Apply initial VRT preset and toggle state
        if hasattr(self, "comboBox_vrtPreset"):
            self._on_vrt_preset_changed(self.comboBox_vrtPreset.currentIndex())
        if hasattr(self, "checkBox_createVrt"):
            self._on_create_vrt_toggled(self.checkBox_createVrt.isChecked())

        self._update_extent_info()
        self._update_vrt_info()

        # Start polling (kept lightweight; only updates when something really changed)
        self._start_extent_polling()
        self._last_layer_id: str | None = None
        self._load_settings()

    def tr(
        self,
        text: str,
        disambiguation: Optional[str] = None,
        n: int = -1,
    ) -> str:
        """Qt translation helper."""
        return QCoreApplication.translate("CustomMapDownloaderDialog", text, disambiguation, n)

    @staticmethod
    def _project() -> QgsProject:
        """Return current QGIS project instance."""
        project = QgsProject.instance()
        if project is None:
            raise RuntimeError("QgsProject instance is unavailable.")
        return project

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _apply_ui_constants(self) -> None:
        """Apply QGIS-typical constraints from constants."""
        if hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.setDecimals(int(GSD_DECIMALS))
            self.spinBox_gsd.setSingleStep(float(GSD_STEP))
            self.spinBox_gsd.setMinimum(float(GSD_MIN))
            self.spinBox_gsd.setMaximum(float(GSD_MAX))

    def _init_output_format_combo(self) -> None:
        """Initialize output format combobox (single export only)."""
        if not hasattr(self, "comboBox_outputFormat"):
            return

        self.comboBox_outputFormat.clear()
        # Store extension as userData
        self.comboBox_outputFormat.addItem(self.tr("GeoTIFF (*.tif)"), ".tif")
        self.comboBox_outputFormat.addItem(self.tr("PNG (*.png)"), ".png")
        self.comboBox_outputFormat.addItem(self.tr("JPEG (*.jpg)"), ".jpg")
        self.comboBox_outputFormat.setCurrentIndex(0)

        # Keep UI state consistent
        self.comboBox_outputFormat.currentIndexChanged.connect(self._update_output_controls_state)
        if hasattr(self, "checkBox_createVrt"):
            self.checkBox_createVrt.toggled.connect(self._update_output_controls_state)

        self._update_output_controls_state()

    def _update_output_controls_state(self) -> None:
        """Enable/disable output format based on VRT mode."""
        create_vrt = bool(self.checkBox_createVrt.isChecked()) if hasattr(self, "checkBox_createVrt") else False
        if hasattr(self, "comboBox_outputFormat"):
            self.comboBox_outputFormat.setEnabled(not create_vrt)

    def _selected_output_extension(self) -> str:
        """Return desired output extension for single export."""
        if hasattr(self, "comboBox_outputFormat"):
            try:
                ext = str(self.comboBox_outputFormat.currentData() or "").strip().lower()
                if ext in {".tif", ".tiff"}:
                    return ".tif"
                if ext in {".jpg", ".jpeg"}:
                    return ".jpg"
                if ext == ".png":
                    return ".png"
            except Exception:
                pass
        return ".tif"

    def _sanitize_prefix(self, prefix: str) -> str:
        """Strip known file extensions from a user-provided prefix."""
        p = (prefix or "").strip()
        if not p:
            return p
        base, ext = os.path.splitext(p)
        if base and ext.lower() in {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".vrt"}:
            return base
        return p

    def _apply_tooltips(self) -> None:
        """Apply QGIS-typical tooltips and What's-This help texts."""
        if hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.setToolTip(
                self.tr(
                    "Pixel size (map units per pixel). Typical: meters per pixel. "
                    "Allowed range: {min} … {max}."
                ).format(min=GSD_MIN, max=GSD_MAX)
            )
            self.spinBox_gsd.setWhatsThis(
                self.tr(
                    "Derived raster size is computed from extent and pixel size. "
                    "For WMTS/XYZ, effective resolution may be snapped to supported zoom levels."
                )
            )

        if hasattr(self, "lineEdit_outputDirectory"):
            self.lineEdit_outputDirectory.setToolTip(self.tr("Target folder for exported files."))
            self.lineEdit_outputDirectory.setWhatsThis(
                self.tr("Select the directory where output files will be written.")
            )

        if hasattr(self, "lineEdit_outputPrefix"):
            self.lineEdit_outputPrefix.setToolTip(self.tr("Base filename without extension."))
            self.lineEdit_outputPrefix.setWhatsThis(
                self.tr(
                    "Provide a filename prefix without extension. "
                    "The extension is selected via 'Output format' (single export) or forced to .vrt in VRT mode."
                )
            )

        if hasattr(self, "comboBox_outputFormat"):
            self.comboBox_outputFormat.setToolTip(self.tr("Output raster format (single export only)."))
            self.comboBox_outputFormat.setWhatsThis(
                self.tr(
                    "GeoTIFF stores georeferencing internally. PNG/JPEG require worldfile + .prj. "
                    "In VRT mode, the output is always a .vrt mosaic and tiles are written as GeoTIFF."
                )
            )

        if hasattr(self, "checkBox_createVrt"):
            self.checkBox_createVrt.setToolTip(
                self.tr("Export tiles + VRT mosaic (VRT-only; no merged single raster).")
            )
            self.checkBox_createVrt.setWhatsThis(
                self.tr("Writes equally sized GeoTIFF tiles and a .vrt file referencing them with relative paths.")
            )

        if hasattr(self, "checkBox_loadLayer"):
            self.checkBox_loadLayer.setToolTip(self.tr("Load the result as a layer after export."))


    # ------------------------------------------------------------------
    # Qt lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Stop polling when the dialog is closed."""
        self._stop_extent_polling()
        super().closeEvent(event)
        self._save_settings()

    def _load_settings(self) -> None:
        """Load last used settings from QSettings."""
        settings = QSettings()
        base = "CustomMapDownloader/"

        try:
            out_dir = settings.value(base + "last_output_dir", "", type=str) or ""
            if out_dir and hasattr(self, "lineEdit_outputDirectory"):
                self.lineEdit_outputDirectory.setText(out_dir)
        except Exception:
            pass

        try:
            gsd = float(settings.value(base + "last_gsd", "", type=float) or 0.0)
            if gsd > 0 and hasattr(self, "spinBox_gsd"):
                self.spinBox_gsd.setValue(gsd)
        except Exception:
            pass

        try:
            crs_authid = settings.value(base + "last_crs", "", type=str) or ""
            if crs_authid and hasattr(self, "mQgsProjectionSelectionWidget"):
                crs = QgsCoordinateReferenceSystem(crs_authid)
                if crs.isValid():
                    self.mQgsProjectionSelectionWidget.setCrs(crs)
        except Exception:
            pass

        try:
            layer_id = settings.value(base + "last_layer_id", "", type=str) or ""
            self._last_layer_id = layer_id or None
        except Exception:
            self._last_layer_id = None

    def _save_settings(self) -> None:
        """Persist last used settings to QSettings."""
        settings = QSettings()
        base = "CustomMapDownloader/"

        if hasattr(self, "lineEdit_outputDirectory"):
            out_dir = (self.lineEdit_outputDirectory.text() or "").strip()
            settings.setValue(base + "last_output_dir", out_dir)

        if hasattr(self, "spinBox_gsd"):
            try:
                settings.setValue(base + "last_gsd", float(self.spinBox_gsd.value()))
            except Exception:
                pass

        try:
            if hasattr(self, "mQgsProjectionSelectionWidget"):
                crs = self.mQgsProjectionSelectionWidget.crs()
                if crs and crs.isValid():
                    settings.setValue(base + "last_crs", crs.authid())
        except Exception:
            pass

        try:
            if hasattr(self, "comboBox_layer"):
                layer = self.comboBox_layer.currentData()
                if layer is not None and hasattr(layer, "id"):
                    settings.setValue(base + "last_layer_id", layer.id())
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Init helpers
    # ------------------------------------------------------------------

    def _init_crs_widgets(self) -> None:
        """Initialize CRS selector widget with project CRS."""
        project_crs = self._project().crs()
        if hasattr(self, "mQgsProjectionSelectionWidget"):
            self.mQgsProjectionSelectionWidget.setCrs(project_crs)

    def _init_extent_group_box(self) -> None:
        """Initialize QgsExtentGroupBox with canvas extent and project CRS."""
        if not hasattr(self, "extentGroupBox"):
            return

        project = self._project()
        canvas = self.iface.mapCanvas()

        try:
            current_rect = canvas.extent()
            current_crs = canvas.mapSettings().destinationCrs()
        except Exception:
            current_crs = project.crs()
            current_rect = QgsRectangle(-1000.0, -1000.0, 1000.0, 1000.0)

        self.extentGroupBox.setMapCanvas(canvas, True)
        self.extentGroupBox.setOriginalExtent(current_rect, current_crs)
        self.extentGroupBox.setCurrentExtent(current_rect, current_crs)
        self.extentGroupBox.setOutputCrs(project.crs())
        self.extentGroupBox.setTitleBase(self.tr("Extent"))
        # Cache internal extent widget + visible line edits for robust extent retrieval.
        self._extent_widget = self._find_extent_widget()
        self._cache_extent_line_edits()

        # When drawing on canvas, QGIS expects the parent dialog to hide/show.
        # Hooking this signal makes "Draw on canvas" much more reliable.
        if self._extent_widget is not None:
            try:
                self._extent_widget.toggleDialogVisibility.connect(self._on_extent_toggle_dialog_visibility)
                self._extent_widget.validationChanged.connect(self._on_extent_validation_changed)
            except Exception:
                pass


    def _hide_project_layer_extent_button(self) -> None:
        """Hide the 'current layer extent' button of QgsExtentGroupBox."""
        if not hasattr(self, "extentGroupBox"):
            return

        keywords_layer = ("layer",)
        keywords_current = ("current", "aktuellen", "aktueller")

        for cls in (QtWidgets.QPushButton, QtWidgets.QToolButton, QtWidgets.QRadioButton):
            for w in self.extentGroupBox.findChildren(cls):
                try:
                    text = (w.text() or "").lower()
                except Exception:
                    continue

                if any(k in text for k in keywords_layer) and any(k in text for k in keywords_current):
                    w.hide()
                    w.setEnabled(False)

    # ------------------------------------------------------------------
    # Polling for extent changes (optional patch)
    # ------------------------------------------------------------------

    def _start_extent_polling(self) -> None:
        """Start polling for extent changes (useful for 'Draw on canvas' mode)."""
        if not hasattr(self, "extentGroupBox"):
            return

        if self._extent_poll_timer is None:
            timer = QTimer(self)
            timer.setInterval(300)
            timer.timeout.connect(self._poll_extent_state)
            self._extent_poll_timer = timer
        else:
            timer = self._extent_poll_timer

        # At this point, `timer` is always a QTimer instance.
        timer.start()

    def _stop_extent_polling(self) -> None:
        """Stop polling timer if running."""
        timer = self._extent_poll_timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

    def _poll_extent_state(self) -> None:
        """Poll extent state and update info labels if it changed."""
        rect = self._get_best_output_extent(commit=False)

        crs: Optional[QgsCoordinateReferenceSystem]
        try:
            crs = self.extentGroupBox.outputCrs() if hasattr(self, "extentGroupBox") else None
        except Exception:
            crs = None

        sig = self._extent_signature(rect, crs)
        if sig == self._last_extent_signature:
            return

        self._last_extent_signature = sig
        self._update_extent_info()
        self._update_vrt_info()

    @staticmethod
    def _extent_signature(
        rect: Optional[QgsRectangle],
        crs: Optional[QgsCoordinateReferenceSystem],
    ) -> Optional[Tuple[float, float, float, float, str]]:
        """Create a stable signature for change detection."""
        if rect is None:
            return None
        if rect.isEmpty() or rect.width() <= 0.0 or rect.height() <= 0.0:
            return None

        authid = ""
        try:
            if crs is not None and crs.isValid():
                authid = crs.authid() or ""
        except Exception:
            authid = ""

        return (
            round(float(rect.xMinimum()), 6),
            round(float(rect.yMinimum()), 6),
            round(float(rect.xMaximum()), 6),
            round(float(rect.yMaximum()), 6),
            authid,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def populate_layers(self) -> None:
        """Populate the layer combobox with all project layers."""
        if not hasattr(self, "comboBox_layer"):
            return

        current_data = self.comboBox_layer.currentData()
        wanted_id = self._last_layer_id
        self.comboBox_layer.clear()

        layers = list(self._project().mapLayers().values())
        for layer in layers:
            self.comboBox_layer.addItem(layer.name(), layer)

        if wanted_id:
            for i in range(self.comboBox_layer.count()):
                lyr = self.comboBox_layer.itemData(i)
                try:
                    if hasattr(lyr, "id") and callable(lyr.id) and lyr.id() == wanted_id:
                        self.comboBox_layer.setCurrentIndex(i)
                        break
                except Exception:
                    continue
        elif current_data is not None:
            for i in range(self.comboBox_layer.count()):
                if self.comboBox_layer.itemData(i) is current_data:
                    self.comboBox_layer.setCurrentIndex(i)
                    break

        if self.comboBox_layer.count() > 0:
            self._on_layer_changed(self.comboBox_layer.currentIndex())

        self.comboBox_layer.setFocus()

    def select_output_directory(self) -> None:
        """Open a dialog to select the output directory."""
        current = ""
        if hasattr(self, "lineEdit_outputDirectory"):
            current = (self.lineEdit_outputDirectory.text() or "").strip()

        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output directory"),
            current or "",
        )
        if directory and hasattr(self, "lineEdit_outputDirectory"):
            self.lineEdit_outputDirectory.setText(directory)

    def get_parameters(self) -> Optional[dict]:
        """Collect and validate dialog parameters."""
        output_directory = (
            self.lineEdit_outputDirectory.text().strip()
            if hasattr(self, "lineEdit_outputDirectory")
            else ""
        )
        output_prefix = (
            self._sanitize_prefix(self.lineEdit_outputPrefix.text().strip())
            if hasattr(self, "lineEdit_outputPrefix")
            else ""
        )

        if not output_directory or not output_prefix:
            return None
        if not os.path.isdir(output_directory):
            return None
        if os.path.sep in output_prefix or (os.altsep and os.altsep in output_prefix):
            return None

        try:
            gsd = float(self.spinBox_gsd.value())
        except Exception:
            return None
        if gsd <= 0.0:
            return None

        if not hasattr(self, "extentGroupBox"):
            return None

        try:
            output_crs = self.extentGroupBox.outputCrs()
        except Exception:
            return None

        rect_out = self._get_best_output_extent(commit=True)
        if rect_out is None or rect_out.isEmpty() or rect_out.width() <= 0.0 or rect_out.height() <= 0.0:
            return None

        project_crs = self._project().crs()

        rect_proj = QgsRectangle(rect_out)
        if output_crs and output_crs.isValid() and project_crs.isValid() and output_crs != project_crs:
            try:
                tr_proj = QgsCoordinateTransform(output_crs, project_crs, self._project())
                rect_proj = tr_proj.transformBoundingBox(rect_out)
            except Exception:
                rect_proj = QgsRectangle(rect_out)

        west = float(rect_proj.xMinimum())
        east = float(rect_proj.xMaximum())
        south = float(rect_proj.yMinimum())
        north = float(rect_proj.yMaximum())
        if west >= east or south >= north:
            return None

        center_proj = rect_proj.center()
        center_x = center_proj.x()
        center_y = center_proj.y()

        width_px, height_px = self._compute_pixel_dimensions()
        if width_px <= 0 or height_px <= 0:
            return None

        level, _warn_msg = self._pixel_size_limit_status(width_px, height_px)
        if level == "strong":
            return None

        layer = self.comboBox_layer.currentData() if hasattr(self, "comboBox_layer") else None
        if layer is None:
            return None

        load_as_layer = bool(self.checkBox_loadLayer.isChecked()) if hasattr(self, "checkBox_loadLayer") else False
        add_georeferencing = (
            bool(self.checkBox_georeferencing.isChecked())
            if hasattr(self, "checkBox_georeferencing")
            else False
        )

        create_vrt = bool(self.checkBox_createVrt.isChecked()) if hasattr(self, "checkBox_createVrt") else False
        vrt_max_cols = int(self.spinBox_vrtMaxCols.value()) if hasattr(self, "spinBox_vrtMaxCols") else 0
        vrt_max_rows = int(self.spinBox_vrtMaxRows.value()) if hasattr(self, "spinBox_vrtMaxRows") else 0
        vrt_preset_size = 0
        if hasattr(self, "comboBox_vrtPreset"):
            try:
                vrt_preset_size = int(self.comboBox_vrtPreset.currentText())
            except Exception:
                vrt_preset_size = 0
        ext = ".vrt" if create_vrt else self._selected_output_extension()
        output_path = os.path.join(output_directory, f"{output_prefix}{ext}")

        # Worldfiles are always written (PNG/JPEG require them). No checkbox in UI.
        add_georeferencing = True

        return {
            "use_extent": True,
            "west": west,
            "east": east,
            "south": south,
            "north": north,
            "northing": center_y,
            "easting": center_x,
            "gsd": gsd,
            "width": width_px,
            "height": height_px,
            "output_directory": output_directory,
            "output_prefix": output_prefix,
            "output_path": output_path,
            "output_extension": ext,
            "output_format": ("VRT" if create_vrt else ext.lstrip(".").upper()),
            "layer": layer,
            "layer_id": layer.id() if layer is not None and hasattr(layer, "id") else "",
            "load_as_layer": load_as_layer,
            "add_georeferencing": add_georeferencing,
            "create_vrt": create_vrt,
            "vrt_max_cols": vrt_max_cols,
            "vrt_max_rows": vrt_max_rows,
            "vrt_preset_size": vrt_preset_size,
            "output_crs": output_crs,
        }

    # ------------------------------------------------------------------
    # Slots / helpers
    # ------------------------------------------------------------------

    def _on_layer_changed(self, index: int) -> None:  # noqa: ARG002
        """Handle layer combobox change and wire QgsExtentGroupBox to the selected layer."""
        layer = None
        if hasattr(self, "comboBox_layer"):
            try:
                layer = self.comboBox_layer.itemData(index)
            except Exception:
                layer = None

        if layer is not None and hasattr(self, "extentGroupBox"):
            try:
                self.extentGroupBox.setLayer(layer)
            except Exception:
                pass
            try:
                self.extentGroupBox.setOutputExtentFromLayer(layer)
            except Exception:
                try:
                    rect = layer.extent()
                    self.extentGroupBox.setCurrentExtent(rect, layer.crs())
                except Exception:
                    pass

        self._update_extent_info()
        self._update_vrt_info()

    def _on_output_crs_changed(self, crs: QgsCoordinateReferenceSystem) -> None:
        """Update extent output CRS when CRS widget changes."""
        if not hasattr(self, "extentGroupBox"):
            return
        try:
            self.extentGroupBox.setOutputCrs(crs)
        except Exception:
            return
        self._update_extent_info()
        self._update_vrt_info()

    def _on_extent_changed(self, _rect: QgsRectangle) -> None:  # noqa: ARG002
        """React to extent changes from QgsExtentGroupBox."""
        self._get_best_output_extent(commit=True)
        self._update_extent_info()
        self._update_vrt_info()

    def _on_create_vrt_toggled(self, enabled: bool) -> None:
        """Enable/disable VRT tiling controls based on checkbox."""
        if hasattr(self, "comboBox_vrtPreset"):
            self.comboBox_vrtPreset.setEnabled(enabled)
        if hasattr(self, "label_vrtPreset"):
            self.label_vrtPreset.setEnabled(enabled)
        if hasattr(self, "spinBox_vrtMaxCols"):
            self.spinBox_vrtMaxCols.setEnabled(enabled)
        if hasattr(self, "label_vrtMaxColumns"):
            self.label_vrtMaxColumns.setEnabled(enabled)
        if hasattr(self, "spinBox_vrtMaxRows"):
            self.spinBox_vrtMaxRows.setEnabled(enabled)
        if hasattr(self, "label_vrtMaxRows"):
            self.label_vrtMaxRows.setEnabled(enabled)
        if hasattr(self, "label_vrtInfo") and not enabled:
            self.label_vrtInfo.setText("")

        self._update_vrt_info()

    def _on_vrt_preset_changed(self, index: int) -> None:  # noqa: ARG002
        """Apply preset tile size from combo box to max columns/rows."""
        if not hasattr(self, "comboBox_vrtPreset"):
            return

        text = self.comboBox_vrtPreset.currentText()
        try:
            size = int(text)
        except (TypeError, ValueError):
            return

        if hasattr(self, "spinBox_vrtMaxCols"):
            self.spinBox_vrtMaxCols.setValue(size)
        if hasattr(self, "spinBox_vrtMaxRows"):
            self.spinBox_vrtMaxRows.setValue(size)

        self._update_vrt_info()

    # ------------------------------------------------------------------
    # Extent resolution helpers (robust for "Draw on canvas")
    # ------------------------------------------------------------------

    @staticmethod
    def _try_parse_float(text: str) -> float:
        """Parse a float from QLineEdit content (locale-aware).

        Supports:
        - German comma decimals ("1,23")
        - Optional thousands separators (spaces, apostrophes)
        - Plain C-locale numbers ("1.23")
        """
        s = (text or "").strip()
        if not s:
            raise ValueError("empty number")

        # Remove common thousands separators
        s = s.replace(" ", "").replace("'", "").replace("_", "")

        # Try system locale first (e.g. de_DE uses comma decimal)
        val, ok = QLocale.system().toDouble(s)
        if ok:
            return float(val)

        # Fallback: try C-locale (dot decimal)
        val, ok = QLocale.c().toDouble(s)
        if ok:
            return float(val)

        # Last resort: normalize comma->dot and let Python parse
        s2 = s.replace(",", ".")
        return float(s2)

    
    def _find_extent_widget(self) -> Optional[QgsExtentWidget]:
        """Return the internal QgsExtentWidget contained in QgsExtentGroupBox."""
        if not hasattr(self, "extentGroupBox"):
            return None
        try:
            return self.extentGroupBox.findChild(QgsExtentWidget)
        except Exception:
            return None

    def _cache_extent_line_edits(self) -> None:
        """Cache the 4 coordinate line edits inside QgsExtentGroupBox.

        Notes:
            This is intentionally cached once to avoid repeated heuristic scans.
            The internal object names / tooltips may vary, so we keep a small
            keyword-based resolver but store the result.
        """
        self._extent_line_edits = {"xmin": None, "xmax": None, "ymin": None, "ymax": None}

        if not hasattr(self, "extentGroupBox"):
            return

        try:
            edits = self.extentGroupBox.findChildren(QtWidgets.QLineEdit)
        except Exception:
            return

        def bag(e: QtWidgets.QLineEdit) -> str:
            parts = [
                (e.objectName() or ""),
                (e.accessibleName() or ""),
                (e.toolTip() or ""),
                (e.placeholderText() or ""),
                (e.statusTip() or ""),
            ]
            return " ".join(p.lower() for p in parts if p)

        # English + German keyword sets (QGIS UI can be localized)
        keys = {
            "xmin": ("xmin", "x min", "min x", "minimum x", "west", "w", "links", "linke"),
            "xmax": ("xmax", "x max", "max x", "maximum x", "east", "e", "rechts", "rechte"),
            "ymin": ("ymin", "y min", "min y", "minimum y", "south", "s", "unten", "untere"),
            "ymax": ("ymax", "y max", "max y", "maximum y", "north", "n", "oben", "obere"),
        }

        # First pass: prefer strong matches in objectName
        for e in edits:
            name = (e.objectName() or "").lower()
            for k, kws in keys.items():
                if any(kw.replace(" ", "") in name.replace("_", "") for kw in kws):
                    if self._extent_line_edits[k] is None:
                        self._extent_line_edits[k] = e

        # Second pass: use the full metadata bag
        for e in edits:
            meta = bag(e)
            for k, kws in keys.items():
                if self._extent_line_edits[k] is not None:
                    continue
                if any(kw in meta for kw in kws):
                    self._extent_line_edits[k] = e

        # If still incomplete: try positional fallback (4 numeric edits)
        if any(v is None for v in self._extent_line_edits.values()):
            numeric_edits = []
            for e in edits:
                t = (e.text() or "").strip()
                if not t:
                    # empty is still fine; check validator / input mask
                    pass
                numeric_edits.append(e)

            # Keep only unique, stable order from Qt
            if len(numeric_edits) >= 4:
                # Best guess: the internal widget usually stores as xmin,xmax,ymin,ymax.
                # We only fill missing slots to avoid breaking already matched ones.
                fallback_order = ["xmin", "xmax", "ymin", "ymax"]
                for slot, e in zip(fallback_order, numeric_edits[:4]):
                    if self._extent_line_edits[slot] is None:
                        self._extent_line_edits[slot] = e

    def _on_extent_toggle_dialog_visibility(self, visible: bool) -> None:
        """Hide/show dialog during 'Draw on canvas' to match QGIS behavior."""
        try:
            self.setVisible(visible)
        except Exception:
            return

        # If drawing just finished, refresh/capture extent and cached edits.
        if visible:
            try:
                self._cache_extent_line_edits()
            except Exception:
                pass
            QTimer.singleShot(0, self._update_extent_info)
            QTimer.singleShot(0, self._update_vrt_info)

    def _on_extent_validation_changed(self, valid: bool) -> None:
        """Called when internal extent widget validation changes."""
        # Keep this lightweight; the polling timer + update methods handle UI.
        _ = valid

    def _extent_from_groupbox_fields(self) -> Optional[QgsRectangle]:
        """Build an extent from the 4 visible line edits inside QgsExtentGroupBox.

        This is a last-resort fallback when outputExtent()/currentExtent() are not
        committed yet (common after 'Draw on canvas').
        """
        if not hasattr(self, "extentGroupBox"):
            return None

        # Ensure we have cached references to the 4 edits
        if not hasattr(self, "_extent_line_edits") or not isinstance(self._extent_line_edits, dict):
            self._cache_extent_line_edits()
        else:
            # Re-cache if any widget got recreated
            if any(v is None for v in self._extent_line_edits.values()):
                self._cache_extent_line_edits()

        e_xmin = self._extent_line_edits.get("xmin")
        e_xmax = self._extent_line_edits.get("xmax")
        e_ymin = self._extent_line_edits.get("ymin")
        e_ymax = self._extent_line_edits.get("ymax")

        # Pylance/typing: explicit None checks so .text() is safe.
        if e_xmin is None or e_xmax is None or e_ymin is None or e_ymax is None:
            return None

        try:
            xmin = self._try_parse_float(e_xmin.text())
            xmax = self._try_parse_float(e_xmax.text())
            ymin = self._try_parse_float(e_ymin.text())
            ymax = self._try_parse_float(e_ymax.text())
        except Exception:
            return None

        rect = QgsRectangle(xmin, ymin, xmax, ymax)
        if rect.isEmpty() or rect.width() <= 0.0 or rect.height() <= 0.0:
            return None

        return rect

    def _get_best_output_extent(self, *, commit: bool) -> Optional[QgsRectangle]:
        """Return the most reliable extent."""
        if not hasattr(self, "extentGroupBox"):
            return None

        rect: Optional[QgsRectangle]

        try:
            rect = self.extentGroupBox.outputExtent()
        except Exception:
            rect = None

        if rect and (not rect.isEmpty()) and rect.width() > 0.0 and rect.height() > 0.0:
            return QgsRectangle(rect)

        try:
            rect = self.extentGroupBox.currentExtent()
        except Exception:
            rect = None

        if rect and (not rect.isEmpty()) and rect.width() > 0.0 and rect.height() > 0.0:
            if commit:
                try:
                    self.extentGroupBox.setCurrentExtent(rect, self.extentGroupBox.outputCrs())
                except Exception:
                    pass
            return QgsRectangle(rect)

        rect2 = self._extent_from_groupbox_fields()
        if rect2 is not None:
            if commit:
                try:
                    self.extentGroupBox.setCurrentExtent(rect2, self.extentGroupBox.outputCrs())
                except Exception:
                    pass
            return QgsRectangle(rect2)

        return None

    # ------------------------------------------------------------------
    # Extent / resolution helpers
    # ------------------------------------------------------------------

    def _get_extent_in_meters(self) -> Tuple[float, float, bool]:
        """Return (width_m, height_m, is_valid) for the current output extent."""
        if not hasattr(self, "extentGroupBox"):
            return 0.0, 0.0, False

        try:
            output_crs = self.extentGroupBox.outputCrs()
        except Exception:
            return 0.0, 0.0, False

        rect = self._get_best_output_extent(commit=False)
        if rect is None or rect.isEmpty() or rect.width() <= 0.0 or rect.height() <= 0.0:
            return 0.0, 0.0, False

        project_crs = self._project().crs()
        source_crs = output_crs if output_crs and output_crs.isValid() else project_crs

        metric_crs = source_crs
        if not self._crs_uses_meters(metric_crs):
            metric_crs = QgsCoordinateReferenceSystem("EPSG:3857")

        try:
            if source_crs.isValid() and metric_crs.isValid() and source_crs != metric_crs:
                tr = QgsCoordinateTransform(source_crs, metric_crs, self._project())
                rect_m = tr.transformBoundingBox(rect)
            else:
                rect_m = rect
        except Exception:
            rect_m = rect

        w_m = float(rect_m.width())
        h_m = float(rect_m.height())
        if w_m <= 0.0 or h_m <= 0.0:
            return 0.0, 0.0, False

        return w_m, h_m, True

    def _compute_pixel_dimensions(self) -> Tuple[int, int]:
        """Compute pixel width/height from extent and GSD."""
        if not hasattr(self, "spinBox_gsd"):
            return 0, 0

        try:
            gsd = float(self.spinBox_gsd.value())
        except Exception:
            return 0, 0
        if gsd <= 0.0:
            return 0, 0

        w_m, h_m, ok = self._get_extent_in_meters()
        if not ok:
            return 0, 0

        width_px = int(round(w_m / gsd))
        height_px = int(round(h_m / gsd))
        return max(1, width_px), max(1, height_px)

    def _update_extent_info(self) -> None:
        """Compute and show derived metrics (physical size and pixel size) for the current extent."""
        if not hasattr(self, "label_extentInfo"):
            return

        w_m, h_m, ok = self._get_extent_in_meters()
        if not ok:
            self._clear_extent_info()
            return

        width_px, height_px = self._compute_pixel_dimensions()
        if width_px <= 0 or height_px <= 0:
            self._clear_extent_info()
            return

        level, warn_msg = pixel_limit_status(width_px, height_px)

        lines = [
            self.tr("Extent: {width:.2f} m × {height:.2f} m").format(width=w_m, height=h_m),
            self.tr("Size: {width_px} × {height_px} px").format(width_px=width_px, height_px=height_px),
        ]
        if warn_msg:
            lines.append(self.tr("Warning: {msg}").format(msg=warn_msg))

        style = ""
        if level == "warn":
            style = "color: #a06000;"
        elif level == "strong":
            style = "color: #a00000;"

        self.label_extentInfo.setText("\n".join(lines))
        self.label_extentInfo.setStyleSheet(style)

    def _update_vrt_info(self) -> None:
        """Compute and show the resulting tile grid when VRT tiling is enabled."""
        if not hasattr(self, "label_vrtInfo"):
            return

        if not hasattr(self, "checkBox_createVrt") or not self.checkBox_createVrt.isChecked():
            self.label_vrtInfo.setText("")
            return

        width_px, height_px = self._compute_pixel_dimensions()
        if width_px <= 0 or height_px <= 0:
            self.label_vrtInfo.setText("")
            return

        try:
            tile_w = int(self.spinBox_vrtMaxCols.value()) if hasattr(self, "spinBox_vrtMaxCols") else 0
            tile_h = int(self.spinBox_vrtMaxRows.value()) if hasattr(self, "spinBox_vrtMaxRows") else 0
        except Exception:
            self.label_vrtInfo.setText("")
            return

        if tile_w <= 0 or tile_h <= 0:
            self.label_vrtInfo.setText("")
            return

        tiles_x = math.ceil(width_px / tile_w)
        tiles_y = math.ceil(height_px / tile_h)
        total = tiles_x * tiles_y
        self.label_vrtInfo.setText(
            self.tr("Tiles: {cols} column(s) × {rows} row(s) = {total} tiles").format(
                cols=tiles_x,
                rows=tiles_y,
                total=total,
            )
        )

    def _clear_extent_info(self) -> None:
        """Clear extent info label to its default informational text."""
        if not hasattr(self, "label_extentInfo"):
            return

        text = self._extent_info_default or "Extent is empty or invalid."
        self.label_extentInfo.setText(self.tr(text))
        self.label_extentInfo.setStyleSheet("color: #a00000;" if not self._extent_info_default else "")

    def _crs_uses_meters(self, crs: QgsCoordinateReferenceSystem) -> bool:
        """Return True if the CRS uses meters as distance unit."""
        try:
            return crs.mapUnits() == Qgis.DistanceUnit.Meters
        except Exception:
            try:
                return QgsUnitTypes.toString(crs.mapUnits()).lower().startswith("meter")
            except Exception:
                return False
