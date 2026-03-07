# CustomMapDownloader/CustomMapDownloader_dialog.py
# -*- coding: utf-8 -*-
"""Dialog for CustomMapDownloader.

Semantics:
- Extent is fully handled by QgsExtentGroupBox (built-in QGIS logic).
- Resolution can be controlled by ground resolution (m/px) or target scale (1:n).
- Pixel dimensions are derived from extent and the active resolution mode.
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

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from qgis.gui import QgsExtentWidget
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QSettings, Qt, QTimer

from .core.constants import (
    GSD_DECIMALS,
    GSD_MAX,
    GSD_MIN,
    GSD_STEP,
)
from .core.profile_io import read_profile, write_profile
from .core.scale import OGC_STANDARD_DPI, gsd_to_scale_denominator, scale_to_gsd_m_per_px
from .core.validation import pixel_limit_status

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
        self._init_resolution_mode_combo()
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
        self._resolution_syncing = False

        # ------------------------------------------------------------------
        # Wire basic UI
        # ------------------------------------------------------------------
        if hasattr(self, "pushButton_browse"):
            self.pushButton_browse.clicked.connect(self.select_output_directory)

        if hasattr(self, "pushButton_refreshLayers"):
            self.pushButton_refreshLayers.clicked.connect(self.populate_layers)

        if hasattr(self, "pushButton_saveProfile"):
            self.pushButton_saveProfile.clicked.connect(self.save_profile)

        if hasattr(self, "pushButton_loadProfile"):
            self.pushButton_loadProfile.clicked.connect(self.load_profile)

        if hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.valueChanged.connect(self._update_extent_info)
            self.spinBox_gsd.valueChanged.connect(self._update_vrt_info)
            self.spinBox_gsd.valueChanged.connect(self._on_gsd_changed)

        if hasattr(self, "comboBox_resolutionMode"):
            self.comboBox_resolutionMode.currentIndexChanged.connect(
                self._on_resolution_mode_changed
            )

        if hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.valueChanged.connect(self._update_extent_info)
            self.doubleSpinBox_targetScale.valueChanged.connect(self._update_vrt_info)
            self.doubleSpinBox_targetScale.valueChanged.connect(self._on_target_scale_changed)

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
        self._update_scale_hint()

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
        if hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.setDecimals(0)
            self.doubleSpinBox_targetScale.setSingleStep(1000.0)
            self.doubleSpinBox_targetScale.setMinimum(1.0)
            self.doubleSpinBox_targetScale.setMaximum(1_000_000_000.0)

    def _init_resolution_mode_combo(self) -> None:
        """Initialize resolution mode selector and derived scale value."""
        if hasattr(self, "comboBox_resolutionMode"):
            self.comboBox_resolutionMode.clear()
            self.comboBox_resolutionMode.addItem(self.tr("GSD (m/px)"), "gsd")
            self.comboBox_resolutionMode.addItem(self.tr("Target scale (1:n)"), "scale")

        if hasattr(self, "spinBox_gsd") and hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.setValue(
                round(gsd_to_scale_denominator(float(self.spinBox_gsd.value())))
            )

        self._update_resolution_controls()

    def _resolution_mode(self) -> str:
        """Return active resolution mode."""
        if hasattr(self, "comboBox_resolutionMode"):
            try:
                mode = str(self.comboBox_resolutionMode.currentData() or "").strip().lower()
            except Exception:
                mode = ""
            if mode in {"gsd", "scale"}:
                return mode
        return "gsd"

    def _update_resolution_controls(self) -> None:
        """Enable only the active resolution input."""
        use_scale = self._resolution_mode() == "scale"
        if hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.setEnabled(not use_scale)
        if hasattr(self, "label_gsd"):
            self.label_gsd.setEnabled(not use_scale)
        if hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.setEnabled(use_scale)
        if hasattr(self, "label_targetScale"):
            self.label_targetScale.setEnabled(use_scale)

    def _current_gsd(self) -> float:
        """Return active GSD in meters per pixel."""
        if self._resolution_mode() == "scale":
            if not hasattr(self, "doubleSpinBox_targetScale"):
                return 0.0
            try:
                scale = float(self.doubleSpinBox_targetScale.value())
            except Exception:
                return 0.0
            return scale_to_gsd_m_per_px(scale)

        if not hasattr(self, "spinBox_gsd"):
            return 0.0
        try:
            return float(self.spinBox_gsd.value())
        except Exception:
            return 0.0

    def _current_target_scale(self) -> Optional[float]:
        """Return target scale denominator for scale mode."""
        if self._resolution_mode() != "scale" or not hasattr(self, "doubleSpinBox_targetScale"):
            return None
        try:
            scale = float(self.doubleSpinBox_targetScale.value())
        except Exception:
            return None
        return scale if scale > 0.0 else None

    def _sync_scale_from_gsd(self, gsd: float) -> None:
        """Update target scale widget from GSD without recursion."""
        if self._resolution_syncing or not hasattr(self, "doubleSpinBox_targetScale") or gsd <= 0.0:
            return
        self._resolution_syncing = True
        try:
            self.doubleSpinBox_targetScale.setValue(round(gsd_to_scale_denominator(gsd)))
        finally:
            self._resolution_syncing = False

    def _sync_gsd_from_scale(self, scale: float) -> None:
        """Update GSD widget from target scale without recursion."""
        if self._resolution_syncing or not hasattr(self, "spinBox_gsd") or scale <= 0.0:
            return
        self._resolution_syncing = True
        try:
            self.spinBox_gsd.setValue(scale_to_gsd_m_per_px(scale))
        finally:
            self._resolution_syncing = False

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
        create_vrt = (
            bool(self.checkBox_createVrt.isChecked())
            if hasattr(self, "checkBox_createVrt")
            else False
        )
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
                    "Ground resolution in map units per pixel. Typical: meters per pixel. "
                    "Allowed range: {min} … {max}."
                ).format(min=GSD_MIN, max=GSD_MAX)
            )
            self.spinBox_gsd.setWhatsThis(
                self.tr(
                    "Derived raster size is computed from extent and pixel size. "
                    "For WMTS/XYZ, effective resolution may be snapped to supported zoom levels."
                )
            )

        if hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.setToolTip(
                self.tr(
                    "Target map scale denominator (1:n). "
                    "Internally converted using the OGC standard pixel size of 0.28 mm."
                )
            )
            self.doubleSpinBox_targetScale.setWhatsThis(
                self.tr(
                    "Use this mode when a WMS changes portrayal by scale. "
                    "The plugin derives GSD from the entered target scale."
                )
            )
        if hasattr(self, "label_scaleHint"):
            self.label_scaleHint.setToolTip(
                self.tr(
                    "Context-sensitive hints for WMS portrayal, CRS choice and VRT limitations."
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

        if hasattr(self, "pushButton_saveProfile"):
            self.pushButton_saveProfile.setToolTip(
                self.tr("Save the current dialog state as a reusable JSON export profile.")
            )

        if hasattr(self, "pushButton_loadProfile"):
            self.pushButton_loadProfile.setToolTip(
                self.tr("Load a previously saved JSON export profile into the dialog.")
            )

        if hasattr(self, "mQgsProjectionSelectionWidget"):
            self.mQgsProjectionSelectionWidget.setToolTip(
                self.tr(
                    "CRS of the exported raster. In target scale mode, choose a projected CRS with meter units."
                )
            )

        if hasattr(self, "comboBox_outputFormat"):
            self.comboBox_outputFormat.setToolTip(
                self.tr("Output raster format (single export only).")
            )
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
                self.tr(
                    "Writes equally sized GeoTIFF tiles and a .vrt file referencing them with relative paths."
                )
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
            target_scale = float(settings.value(base + "last_target_scale", "", type=float) or 0.0)
            if target_scale > 0 and hasattr(self, "doubleSpinBox_targetScale"):
                self.doubleSpinBox_targetScale.setValue(target_scale)
        except Exception:
            pass

        try:
            resolution_mode = (
                settings.value(base + "last_resolution_mode", "gsd", type=str) or "gsd"
            )
            if hasattr(self, "comboBox_resolutionMode"):
                idx = self.comboBox_resolutionMode.findData(resolution_mode)
                if idx >= 0:
                    self.comboBox_resolutionMode.setCurrentIndex(idx)
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

        self._update_scale_hint()

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

        if hasattr(self, "doubleSpinBox_targetScale"):
            try:
                settings.setValue(
                    base + "last_target_scale", float(self.doubleSpinBox_targetScale.value())
                )
            except Exception:
                pass

        if hasattr(self, "comboBox_resolutionMode"):
            try:
                settings.setValue(base + "last_resolution_mode", self._resolution_mode())
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
                self._extent_widget.toggleDialogVisibility.connect(
                    self._on_extent_toggle_dialog_visibility
                )
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

                if any(k in text for k in keywords_layer) and any(
                    k in text for k in keywords_current
                ):
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

    def _default_profile_path(self) -> str:
        """Return a sensible default path for save/load profile dialogs."""
        output_directory = ""
        if hasattr(self, "lineEdit_outputDirectory"):
            output_directory = (self.lineEdit_outputDirectory.text() or "").strip()
        if not output_directory or not os.path.isdir(output_directory):
            output_directory = os.path.expanduser("~")

        prefix = ""
        if hasattr(self, "lineEdit_outputPrefix"):
            prefix = self._sanitize_prefix(self.lineEdit_outputPrefix.text())
        prefix = prefix or "custom_map_download"
        return os.path.join(output_directory, f"{prefix}.cmdprofile.json")

    def _set_output_format_from_extension(self, extension: str) -> None:
        """Select output format combo entry from a file extension."""
        if not hasattr(self, "comboBox_outputFormat"):
            return
        wanted = (extension or "").strip().lower()
        for idx in range(self.comboBox_outputFormat.count()):
            try:
                current = str(self.comboBox_outputFormat.itemData(idx) or "").strip().lower()
            except Exception:
                continue
            if current == wanted:
                self.comboBox_outputFormat.setCurrentIndex(idx)
                return

    def _select_layer_from_profile(self, layer_id: str, layer_name: str) -> list[str]:
        """Restore selected layer from stored id/name if possible."""
        warnings: list[str] = []
        if not hasattr(self, "comboBox_layer"):
            return warnings

        selected_index = -1
        for idx in range(self.comboBox_layer.count()):
            layer = self.comboBox_layer.itemData(idx)
            try:
                if (
                    layer_id
                    and hasattr(layer, "id")
                    and callable(layer.id)
                    and layer.id() == layer_id
                ):
                    selected_index = idx
                    break
            except Exception:
                continue

        if selected_index < 0 and layer_name:
            for idx in range(self.comboBox_layer.count()):
                layer = self.comboBox_layer.itemData(idx)
                try:
                    if (
                        hasattr(layer, "name")
                        and callable(layer.name)
                        and layer.name() == layer_name
                    ):
                        selected_index = idx
                        break
                except Exception:
                    continue

        if selected_index >= 0:
            self.comboBox_layer.setCurrentIndex(selected_index)
        elif layer_id or layer_name:
            warnings.append(
                self.tr("Stored layer could not be restored. Please choose a layer manually.")
            )

        return warnings

    def _collect_profile_state(self) -> dict:
        """Capture current dialog state for JSON profile export."""
        state = {
            "output_directory": (
                (self.lineEdit_outputDirectory.text() or "").strip()
                if hasattr(self, "lineEdit_outputDirectory")
                else ""
            ),
            "output_prefix": (
                self._sanitize_prefix(self.lineEdit_outputPrefix.text())
                if hasattr(self, "lineEdit_outputPrefix")
                else ""
            ),
            "output_extension": self._selected_output_extension(),
            "resolution_mode": self._resolution_mode(),
            "gsd": self._current_gsd(),
            "target_scale_denominator": self._current_target_scale(),
            "load_as_layer": (
                bool(self.checkBox_loadLayer.isChecked())
                if hasattr(self, "checkBox_loadLayer")
                else False
            ),
            "create_vrt": (
                bool(self.checkBox_createVrt.isChecked())
                if hasattr(self, "checkBox_createVrt")
                else False
            ),
            "vrt_max_cols": (
                int(self.spinBox_vrtMaxCols.value()) if hasattr(self, "spinBox_vrtMaxCols") else 0
            ),
            "vrt_max_rows": (
                int(self.spinBox_vrtMaxRows.value()) if hasattr(self, "spinBox_vrtMaxRows") else 0
            ),
            "vrt_preset_size": 0,
            "layer_id": "",
            "layer_name": "",
            "output_crs_authid": "",
            "extent": None,
        }

        if hasattr(self, "comboBox_vrtPreset"):
            try:
                state["vrt_preset_size"] = int(self.comboBox_vrtPreset.currentText())
            except Exception:
                state["vrt_preset_size"] = 0

        if hasattr(self, "comboBox_layer"):
            layer = self.comboBox_layer.currentData()
            try:
                if layer is not None and hasattr(layer, "id") and callable(layer.id):
                    state["layer_id"] = layer.id()
            except Exception:
                pass
            try:
                if layer is not None and hasattr(layer, "name") and callable(layer.name):
                    state["layer_name"] = layer.name()
            except Exception:
                pass

        try:
            output_crs = (
                self.extentGroupBox.outputCrs() if hasattr(self, "extentGroupBox") else None
            )
            if output_crs is not None and output_crs.isValid():
                state["output_crs_authid"] = output_crs.authid() or ""
        except Exception:
            pass

        rect = self._get_best_output_extent(commit=False)
        if rect is not None and not rect.isEmpty() and rect.width() > 0.0 and rect.height() > 0.0:
            state["extent"] = {
                "west": float(rect.xMinimum()),
                "south": float(rect.yMinimum()),
                "east": float(rect.xMaximum()),
                "north": float(rect.yMaximum()),
            }

        return state

    def _apply_profile_state(self, profile: dict) -> list[str]:
        """Apply a previously stored dialog profile."""
        warnings: list[str] = []

        if hasattr(self, "lineEdit_outputDirectory"):
            self.lineEdit_outputDirectory.setText(str(profile.get("output_directory") or ""))

        if hasattr(self, "lineEdit_outputPrefix"):
            self.lineEdit_outputPrefix.setText(str(profile.get("output_prefix") or ""))

        self._set_output_format_from_extension(str(profile.get("output_extension") or ".tif"))

        resolution_mode = str(profile.get("resolution_mode") or "gsd")
        if hasattr(self, "comboBox_resolutionMode"):
            idx = self.comboBox_resolutionMode.findData(resolution_mode)
            if idx >= 0:
                self.comboBox_resolutionMode.setCurrentIndex(idx)

        gsd = profile.get("gsd")
        if gsd is not None and hasattr(self, "spinBox_gsd"):
            self.spinBox_gsd.setValue(float(gsd))

        target_scale = profile.get("target_scale_denominator")
        if target_scale is not None and hasattr(self, "doubleSpinBox_targetScale"):
            self.doubleSpinBox_targetScale.setValue(float(target_scale))

        if hasattr(self, "checkBox_loadLayer"):
            self.checkBox_loadLayer.setChecked(bool(profile.get("load_as_layer")))

        if hasattr(self, "checkBox_createVrt"):
            self.checkBox_createVrt.setChecked(bool(profile.get("create_vrt")))

        if hasattr(self, "spinBox_vrtMaxCols"):
            self.spinBox_vrtMaxCols.setValue(int(profile.get("vrt_max_cols") or 0))

        if hasattr(self, "spinBox_vrtMaxRows"):
            self.spinBox_vrtMaxRows.setValue(int(profile.get("vrt_max_rows") or 0))

        if hasattr(self, "comboBox_vrtPreset"):
            preset_size = int(profile.get("vrt_preset_size") or 0)
            if preset_size > 0:
                preset_text = str(preset_size)
                idx = self.comboBox_vrtPreset.findText(preset_text)
                if idx >= 0:
                    self.comboBox_vrtPreset.setCurrentIndex(idx)

        warnings.extend(
            self._select_layer_from_profile(
                str(profile.get("layer_id") or ""),
                str(profile.get("layer_name") or ""),
            )
        )

        crs_authid = str(profile.get("output_crs_authid") or "")
        if crs_authid and hasattr(self, "mQgsProjectionSelectionWidget"):
            crs = QgsCoordinateReferenceSystem(crs_authid)
            if crs.isValid():
                self.mQgsProjectionSelectionWidget.setCrs(crs)
            else:
                warnings.append(self.tr("Stored CRS could not be restored."))

        extent = profile.get("extent")
        if isinstance(extent, dict) and hasattr(self, "extentGroupBox"):
            try:
                crs = self.extentGroupBox.outputCrs()
                rect = QgsRectangle(
                    float(extent["west"]),
                    float(extent["south"]),
                    float(extent["east"]),
                    float(extent["north"]),
                )
                self.extentGroupBox.setCurrentExtent(rect, crs)
            except Exception:
                warnings.append(self.tr("Stored extent could not be restored."))

        self._update_resolution_controls()
        self._update_output_controls_state()
        self._update_extent_info()
        self._update_vrt_info()
        self._update_scale_hint()
        return warnings

    def save_profile(self) -> None:
        """Save current dialog state as JSON profile."""
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            self.tr("Save export profile"),
            self._default_profile_path(),
            self.tr(
                "Custom Map Downloader profile (*.cmdprofile.json *.json);;JSON files (*.json)"
            ),
        )
        if not path:
            return
        try:
            write_profile(path, self._collect_profile_state())
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                self.tr("Save profile failed"),
                self.tr("Could not save profile:\n{msg}").format(msg=str(exc)),
            )

    def load_profile(self) -> None:
        """Load dialog state from JSON profile."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("Load export profile"),
            self._default_profile_path(),
            self.tr(
                "Custom Map Downloader profile (*.cmdprofile.json *.json);;JSON files (*.json)"
            ),
        )
        if not path:
            return
        try:
            profile = read_profile(path)
            warnings = self._apply_profile_state(profile)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                self.tr("Load profile failed"),
                self.tr("Could not load profile:\n{msg}").format(msg=str(exc)),
            )
            return

        if warnings:
            QtWidgets.QMessageBox.warning(
                self,
                self.tr("Profile loaded with warnings"),
                "\n".join(warnings),
            )

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

        gsd = self._current_gsd()
        if gsd <= 0.0:
            return None

        if not hasattr(self, "extentGroupBox"):
            return None

        try:
            output_crs = self.extentGroupBox.outputCrs()
        except Exception:
            return None

        rect_out = self._get_best_output_extent(commit=True)
        if (
            rect_out is None
            or rect_out.isEmpty()
            or rect_out.width() <= 0.0
            or rect_out.height() <= 0.0
        ):
            return None

        project_crs = self._project().crs()

        rect_proj = QgsRectangle(rect_out)
        if (
            output_crs
            and output_crs.isValid()
            and project_crs.isValid()
            and output_crs != project_crs
        ):
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

        load_as_layer = (
            bool(self.checkBox_loadLayer.isChecked())
            if hasattr(self, "checkBox_loadLayer")
            else False
        )
        add_georeferencing = (
            bool(self.checkBox_georeferencing.isChecked())
            if hasattr(self, "checkBox_georeferencing")
            else False
        )

        create_vrt = (
            bool(self.checkBox_createVrt.isChecked())
            if hasattr(self, "checkBox_createVrt")
            else False
        )
        vrt_max_cols = (
            int(self.spinBox_vrtMaxCols.value()) if hasattr(self, "spinBox_vrtMaxCols") else 0
        )
        vrt_max_rows = (
            int(self.spinBox_vrtMaxRows.value()) if hasattr(self, "spinBox_vrtMaxRows") else 0
        )
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
            "target_scale_denominator": self._current_target_scale(),
            "output_dpi": OGC_STANDARD_DPI if self._resolution_mode() == "scale" else None,
            "resolution_mode": self._resolution_mode(),
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

    def _on_resolution_mode_changed(self, _index: int) -> None:
        """Toggle the active resolution input."""
        self._update_resolution_controls()
        self._update_extent_info()
        self._update_vrt_info()
        self._update_scale_hint()

    def _on_gsd_changed(self, value: float) -> None:
        """Keep scale denominator synchronized when GSD changes."""
        self._sync_scale_from_gsd(float(value))

    def _on_target_scale_changed(self, value: float) -> None:
        """Keep GSD synchronized when target scale changes."""
        self._sync_gsd_from_scale(float(value))

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
        self._update_scale_hint()

    def _on_extent_changed(self, _rect: QgsRectangle) -> None:  # noqa: ARG002
        """React to extent changes from QgsExtentGroupBox."""
        self._get_best_output_extent(commit=True)
        self._update_extent_info()
        self._update_vrt_info()
        self._update_scale_hint()

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
        self._update_scale_hint()

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
                for slot, e in zip(fallback_order, numeric_edits[:4], strict=False):
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
            QTimer.singleShot(0, self._update_scale_hint)

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
        gsd = self._current_gsd()
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
            self.tr("GSD: {gsd:.4f} m/px").format(gsd=self._current_gsd()),
            self.tr("Size: {width_px} × {height_px} px").format(
                width_px=width_px, height_px=height_px
            ),
        ]
        target_scale = self._current_target_scale()
        if target_scale is not None:
            lines.insert(2, self.tr("Target scale: 1:{scale:.0f}").format(scale=target_scale))
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
            tile_w = (
                int(self.spinBox_vrtMaxCols.value()) if hasattr(self, "spinBox_vrtMaxCols") else 0
            )
            tile_h = (
                int(self.spinBox_vrtMaxRows.value()) if hasattr(self, "spinBox_vrtMaxRows") else 0
            )
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

    def _layer_looks_scale_sensitive(self) -> bool:
        """Best-effort heuristic for web map sources that can vary by scale."""
        if not hasattr(self, "comboBox_layer"):
            return False
        layer = self.comboBox_layer.currentData()
        if layer is None:
            return False

        provider = ""
        source = ""
        try:
            if hasattr(layer, "providerType") and callable(layer.providerType):
                provider = str(layer.providerType() or "").strip().lower()
        except Exception:
            provider = ""
        try:
            if hasattr(layer, "source") and callable(layer.source):
                source = str(layer.source() or "").strip().lower()
        except Exception:
            source = ""

        if provider in {"wms", "xyz", "arcgismapserver"}:
            return True
        return "type=xyz" in source or "contextualwmslegend" in source or "url=" in source

    def _output_crs_uses_meters(self) -> bool:
        """Return True when the selected output CRS uses meters."""
        try:
            crs = self.mQgsProjectionSelectionWidget.crs()
        except Exception:
            return False
        return bool(crs and crs.isValid() and self._crs_uses_meters(crs))

    def _update_scale_hint(self) -> None:
        """Update contextual hints for scale-sensitive services and CRS limitations."""
        if not hasattr(self, "label_scaleHint"):
            return

        use_scale = self._resolution_mode() == "scale"
        create_vrt = (
            bool(self.checkBox_createVrt.isChecked())
            if hasattr(self, "checkBox_createVrt")
            else False
        )
        metric_output = self._output_crs_uses_meters()
        scale_sensitive = self._layer_looks_scale_sensitive()

        lines: list[str] = []
        style = "color: #666;"

        if use_scale and not metric_output:
            style = "color: #b00020; font-weight: 600;"
            lines.append(
                self.tr("Target scale mode needs a projected output CRS with meter units.")
            )
        else:
            if use_scale and scale_sensitive:
                style = "color: #8a5a00;"
                lines.append(
                    self.tr(
                        "This layer may change portrayal by scale. Target scale mode is appropriate here."
                    )
                )
            if scale_sensitive and not metric_output:
                style = "color: #8a5a00;"
                lines.append(
                    self.tr(
                        "With a non-metric output CRS, the plugin may render internally in a metric CRS and reproject the final raster."
                    )
                )
            if create_vrt and not metric_output:
                style = "color: #8a5a00;"
                lines.append(
                    self.tr(
                        "VRT export is most predictable when render CRS and output CRS are identical."
                    )
                )

        self.label_scaleHint.setText("\n".join(lines))
        self.label_scaleHint.setVisible(bool(lines))
        self.label_scaleHint.setStyleSheet(style)

    def _clear_extent_info(self) -> None:
        """Clear extent info label to its default informational text."""
        if not hasattr(self, "label_extentInfo"):
            return

        text = self._extent_info_default or "Extent is empty or invalid."
        self.label_extentInfo.setText(self.tr(text))
        self.label_extentInfo.setStyleSheet(
            "color: #a00000;" if not self._extent_info_default else ""
        )

    def _crs_uses_meters(self, crs: QgsCoordinateReferenceSystem) -> bool:
        """Return True if the CRS uses meters as distance unit."""
        try:
            return crs.mapUnits() == Qgis.DistanceUnit.Meters
        except Exception:
            try:
                return QgsUnitTypes.toString(crs.mapUnits()).lower().startswith("meter")
            except Exception:
                return False
