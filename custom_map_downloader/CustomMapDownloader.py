# CustomMapDownloader/CustomMapDownloader.py
# -*- coding: utf-8 -*-
"""
Main plugin implementation for the CustomMapDownloader QGIS plugin.

Notes:
    - Extent is defined exclusively via QgsExtentGroupBox in the dialog.
    - The dialog provides:
        * extent (west/east/south/north) in project CRS,
        * ground resolution (m/px) or target scale (1:n),
        * optional VRT/tiling parameters (create_vrt, vrt_max_cols,
          vrt_max_rows, vrt_preset_size).
    - These parameters are threaded into ExportParams.
"""

import os
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsNetworkAccessManager,
    QgsProject,
    QgsRasterLayer,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTranslator
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QCheckBox, QMessageBox, QProgressDialog

from .core.errors import CancelledError, ExportError, ValidationError
from .core.exporter import GeoTiffExporter
from .core.locale import resolve_locale_code
from .core.models import CancelToken, CenterSpec, ExportParams, ExtentSpec
from .CustomMapDownloader_dialog import CustomMapDownloaderDialog
from .resources import *  # noqa: F401,F403


class CustomMapDownloader:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """
        Constructor.

        Args:
            iface: QGIS interface instance.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.translator: QTranslator | None = None

        # i18n / Locale
        locale = resolve_locale_code(QSettings().value("locale/userLocale"))
        locale_path = os.path.join(self.plugin_dir, "i18n", f"CustomMapDownloader_{locale}.qm")

        if os.path.exists(locale_path):
            translator = QTranslator()
            translator.load(locale_path)
            QCoreApplication.installTranslator(translator)
            self.translator = translator

        self.actions = []
        self.menu = self.tr("&MapDownloader")
        self.first_start = None
        self.dlg: CustomMapDownloaderDialog | None = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message: str) -> str:
        """Translate a message."""
        return QCoreApplication.translate("CustomMapDownloader", message)

    @staticmethod
    def _project() -> QgsProject:
        """Return current QGIS project instance."""
        project = QgsProject.instance()
        if project is None:
            raise RuntimeError("QgsProject instance is unavailable.")
        return project

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon and/or a menu entry."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self) -> None:
        """Create menu entries and toolbar icons in QGIS."""
        icon_path = ":/plugins/CustomMapDownloader/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("Download GeoTIFF from Map"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )
        self.first_start = True

    def unload(self) -> None:
        """Remove the plugin from the QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&MapDownloader"), action)
            self.iface.removeToolBarIcon(action)

    def run(self) -> None:
        """Open dialog, validate user input, and start export."""
        # Lazily create dialog
        if self.dlg is None:
            self.dlg = CustomMapDownloaderDialog(self.iface)

        # Always refresh layer list
        self.dlg.populate_layers()

        self.dlg.show()
        result = self.dlg.exec_()
        if not result:
            return

        # Retrieve parameters from dialog
        params = self.dlg.get_parameters()
        if params is None:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Error"),
                self.tr("Invalid input parameters. Please check values."),
            )
            return

        # Determine actual render/output CRS.
        # Scale-dependent WMS rendering is only reliable in a projected metric CRS.
        project_crs = self._project().crs()
        try:
            project_is_meters = project_crs.mapUnits() == Qgis.DistanceUnit.Meters
        except Exception:
            project_is_meters = (
                QgsUnitTypes.toString(project_crs.mapUnits()).lower().startswith("meter")
            )

        selected_output_crs = params.get("output_crs")
        selected_output_is_meters = False
        if selected_output_crs is not None:
            try:
                selected_output_is_meters = (
                    selected_output_crs.isValid()
                    and selected_output_crs.mapUnits() == Qgis.DistanceUnit.Meters
                )
            except Exception:
                selected_output_is_meters = False

        requested_scale = params.get("target_scale_denominator")
        if requested_scale is not None and not selected_output_is_meters:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Error"),
                self.tr(
                    "Target scale mode requires a projected output CRS with meter units. "
                    "Please choose a metric CRS such as EPSG:3857 or a local projected CRS."
                ),
            )
            return

        requested_output_crs = (
            selected_output_crs
            if selected_output_crs is not None and selected_output_crs.isValid()
            else None
        )

        if selected_output_is_meters:
            render_crs = selected_output_crs
        elif project_crs.isValid() and project_is_meters:
            render_crs = project_crs
        else:
            render_crs = QgsCoordinateReferenceSystem("EPSG:3857")

        output_crs = requested_output_crs or render_crs

        # Center in project CRS (as provided by dialog)
        center = CenterSpec(
            northing=float(params["northing"]),  # Y
            easting=float(params["easting"]),  # X
            crs=project_crs,
        )

        # Extent in project CRS
        extent = ExtentSpec(
            west=float(params["west"]),
            south=float(params["south"]),
            east=float(params["east"]),
            north=float(params["north"]),
            crs=project_crs,
        )

        # Optional VRT / tiling parameters from dialog
        create_vrt = bool(params.get("create_vrt", False))
        vrt_max_cols = int(params.get("vrt_max_cols", 0) or 0)
        vrt_max_rows = int(params.get("vrt_max_rows", 0) or 0)
        vrt_preset_size = int(params.get("vrt_preset_size", 0) or 0)

        export_params = ExportParams(
            layer=params["layer"],
            width_px=int(params["width"]),
            height_px=int(params["height"]),
            gsd_m_per_px=float(params["gsd"]),
            center=center,
            extent=extent,
            output_path=params["output_path"],
            load_as_layer=bool(params["load_as_layer"]),
            render_crs=render_crs,
            output_crs=output_crs,
            target_scale_denominator=params.get("target_scale_denominator"),
            output_dpi=params.get("output_dpi"),
            create_vrt=create_vrt,
            vrt_max_cols=vrt_max_cols,
            vrt_max_rows=vrt_max_rows,
            vrt_preset_size=vrt_preset_size,
        )

        conflicts = self._find_loaded_layer_conflicts(
            export_params.output_path,
            create_vrt=bool(export_params.create_vrt),
        )
        if conflicts:
            lines = []
            for name, src, reason in conflicts:
                if reason == "direct":
                    lines.append(self.tr("- {name}: {src}").format(name=name, src=src))
                else:
                    lines.append(
                        self.tr(
                            "- {name}: {src} (VRT references files that would be overwritten)"
                        ).format(name=name, src=src)
                    )
            details = "\n".join(lines)

            QMessageBox.warning(
                self.iface.mainWindow(),
                self.tr("Output is currently loaded"),
                self.tr(
                    "One or more raster layers are currently using output files (directly or via VRT references).\n\n"
                    "Please remove these layers (or choose a different output name) and try again:\n\n{details}"
                ).format(details=details),
            )
            return

        # Pre-export summary/confirmation
        if not self._confirm_export(params, export_params):
            return

        try:
            # Persist last-used settings
            if hasattr(self.dlg, "_save_settings"):
                self.dlg._save_settings()
        except Exception:
            pass

        # Progress dialog
        progress = QProgressDialog(
            self.tr("Export running..."),
            self.tr("Cancel"),
            0,
            100,
            self.iface.mainWindow(),
        )
        progress.setWindowTitle(self.tr("Custom Map Downloader"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        cancel_token = CancelToken()
        progress.canceled.connect(cancel_token.cancel)

        export_warnings: list[str] = []

        def progress_cb(percent: int, key: str, args: dict[str, Any]):
            """Progress callback wired to the exporter."""
            args = args or {}
            is_warning = False

            if key == "WARN_TILE_RETRY":
                attempt = args.get("attempt", 0)
                max_ = args.get("max", 0)
                seconds = float(args.get("seconds", 0.0) or 0.0)
                msg = self.tr("Retry tile ({a}/{m}) – waiting {s:.1f}s...").format(
                    a=attempt,
                    m=max_,
                    s=seconds,
                )

            elif key == "WARN_LARGE_EXPORT":
                mb = float(args.get("bytes", 0) or 0.0) / (1024 * 1024)
                msg = self.tr("Warning: Very large export (raw approx. {mb:.0f} MB).").format(
                    mb=mb,
                )

            elif key == "WARN_VRT_ABSOLUTE_PATHS":
                is_warning = True
                msg = self.tr(
                    "Warning: The VRT was created, but tile paths could not be rewritten to relative paths. "
                    "The VRT may not be portable."
                )

            else:
                templates = {k: self.tr(v) for k, v in PROGRESS_TEMPLATES.items()}
                tmpl = templates.get(key, key)
                try:
                    msg = tmpl.format(**args)
                except Exception:
                    msg = tmpl

            if is_warning and msg not in export_warnings:
                export_warnings.append(msg)

            progress.setLabelText(msg)
            progress.setValue(int(percent))
            QCoreApplication.processEvents()

        try:
            exporter = GeoTiffExporter()

            # Increase network timeout for slow WMS/XYZ services
            old_timeout = QgsNetworkAccessManager.timeout()
            QgsNetworkAccessManager.setTimeout(10 * 60 * 1000)  # 10 minutes
            try:
                result_path = exporter.export(
                    export_params, progress_cb=progress_cb, cancel_token=cancel_token
                )
            finally:
                QgsNetworkAccessManager.setTimeout(old_timeout)

            # Note: With "Create VRT" enabled, exporter returns the .vrt path.
            saved_path = result_path

            if params["load_as_layer"]:
                layer_name = os.path.basename(saved_path)
                raster_layer = QgsRasterLayer(saved_path, layer_name)

                if raster_layer.isValid():
                    self._project().addMapLayer(raster_layer)
                    success_message = self.tr(
                        "Raster successfully saved and loaded:\n{path}"
                    ).format(
                        path=saved_path,
                    )
                    if export_warnings:
                        success_message = self.tr("{base}\n\nWarnings:\n{warnings}").format(
                            base=success_message,
                            warnings="\n".join(export_warnings),
                        )
                    QMessageBox.information(
                        self.iface.mainWindow(),
                        self.tr("Success"),
                        success_message,
                    )
                else:
                    partial_message = self.tr("Raster saved but loading failed:\n{path}").format(
                        path=saved_path,
                    )
                    if export_warnings:
                        partial_message = self.tr("{base}\n\nWarnings:\n{warnings}").format(
                            base=partial_message,
                            warnings="\n".join(export_warnings),
                        )
                    QMessageBox.warning(
                        self.iface.mainWindow(),
                        self.tr("Partial success"),
                        partial_message,
                    )
            else:
                success_message = self.tr("Raster successfully saved to:\n{path}").format(
                    path=saved_path,
                )
                if export_warnings:
                    success_message = self.tr("{base}\n\nWarnings:\n{warnings}").format(
                        base=success_message,
                        warnings="\n".join(export_warnings),
                    )
                QMessageBox.information(
                    self.iface.mainWindow(),
                    self.tr("Success"),
                    success_message,
                )

        except CancelledError:
            QMessageBox.information(
                self.iface.mainWindow(),
                self.tr("Cancelled"),
                self.tr("Export was cancelled."),
            )

        except ValidationError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Error"),
                self._format_export_error(e),
            )

        except ExportError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Error"),
                self._format_export_error(e),
            )

        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                self.tr("Error"),
                self.tr("Unexpected failure:\n{msg}").format(msg=str(e)),
            )

        finally:
            progress.close()

    def _format_export_error(self, err: ExportError) -> str:
        """Convert exporter errors into user-facing messages."""
        code = getattr(err, "code", "ERR_UNKNOWN")
        details = getattr(err, "details", "")

        messages = {
            "ERR_CANCELLED": self.tr("Export was cancelled."),
            "ERR_VALIDATION_LAYER_MISSING": self.tr("Please select a layer."),
            "ERR_VALIDATION_SIZE_INVALID": self.tr("Invalid output size (width/height)."),
            "ERR_VALIDATION_SIZE_TOO_LARGE": self.tr("Requested raster is too large."),
            "ERR_VALIDATION_GSD_INVALID": self.tr("Invalid GSD value."),
            "ERR_VALIDATION_OUTPUT_MISSING": self.tr("Output path missing."),
            "ERR_VALIDATION_OUTPUT_DIR": self.tr("Output directory is invalid or not writable."),
            "ERR_VALIDATION_OUTPUT_EXT": self.tr("Unsupported output file extension."),
            "ERR_VALIDATION_EXTENT_INVALID": self.tr("Invalid extent values."),
            "ERR_VALIDATION_EXTENT_TRANSFORM_FAILED": self.tr("Failed to transform extent."),
            "ERR_VALIDATION_CENTER_MISSING": self.tr("Center coordinate missing."),
            "ERR_VALIDATION_CENTER_TRANSFORM_FAILED": self.tr(
                "Failed to transform center coordinate."
            ),
            "ERR_VALIDATION_RENDER_CRS_UNITS": self.tr(
                "The selected render CRS does not use meters. Please use a projected CRS."
            ),
            "ERR_VALIDATION_VRT_OUTPUT_CRS_UNSUPPORTED": self.tr(
                "VRT export currently requires identical render and output CRS."
            ),
            "ERR_IMAGE_SAVE_FAILED": self.tr("Failed to write TIFF."),
            "ERR_GDAL_CREATE_FAILED": self.tr("Failed to create GeoTIFF."),
            "ERR_CRS_INVALID": self.tr("Invalid CRS."),
            "ERR_CRS_TO_WKT_FAILED": self.tr("Failed to convert CRS to WKT."),
            "ERR_WARP_FAILED": self.tr(
                "Failed to reproject the rendered raster into the requested output CRS."
            ),
            "ERR_RENDER_EMPTY": self.tr(
                "Rendered image is empty/transparent (often a server limit or timeout)."
            ),
            "ERR_RENDER_FAILED": self.tr("Rendering failed."),
            "ERR_RENDER_TILE_FAILED": self.tr("Tile rendering failed."),
            "ERR_VRT_BUILD_FAILED": self.tr("Failed to build VRT mosaic."),
            "ERR_SIDECAR_WRITE_FAILED": self.tr(
                "Raster export succeeded, but georeferencing sidecar files could not be written."
            ),
        }

        base = messages.get(code, self.tr("Export failed."))
        if details:
            return self.tr("{base}\n\nDetails:\n{details}").format(base=base, details=details)
        return base

    def _find_loaded_layer_conflicts(
        self, output_path: str, *, create_vrt: bool
    ) -> list[tuple[str, str, str]]:
        """Prüfe, ob Ziel-Dateien (direkt oder indirekt via geladenem VRT) aktuell als Layer geladen sind.

        - Direkt-Konflikt: geladener Layer = genau die Datei, die überschrieben werden soll.
        - Indirekt-Konflikt: geladener Layer ist ein .vrt, das Tiles referenziert, die überschrieben werden sollen.

        Args:
            output_path: Pfad aus dem Dialog.
            create_vrt: True => es wird <base>.vrt + Tiles geschrieben, False => einzelnes TIF.

        Returns:
            Liste aus (layer_name, layer_source, reason).
        """
        base = Path(output_path).with_suffix("")
        targets: set[str] = set()

        if create_vrt:
            targets.add(str(base.with_suffix(".vrt")))
            # Tiles, die wir (voraussichtlich) überschreiben würden (nur vorhandene zählen => realer Konflikt möglich)
            for p in base.parent.glob(f"{base.name}__tile_r*_c*.tif"):
                targets.add(str(p))
        else:
            targets.add(str(Path(output_path)))

        def norm_path(p: str) -> str:
            # QGIS raster source kann "path|option=..." sein
            p2 = (p or "").split("|", 1)[0].strip()
            # file:// URI grob abfangen
            if p2.lower().startswith("file://"):
                p2 = p2[7:]
            return os.path.normcase(os.path.abspath(p2))

        targets_norm = {norm_path(p) for p in targets}

        def parse_vrt_references(vrt_path: str) -> set[str]:
            """Parse <SourceFilename> in VRT and return normalized absolute file paths."""
            vrt_file = Path(vrt_path)
            if not vrt_file.exists():
                return set()

            try:
                root = ET.fromstring(vrt_file.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                return set()

            refs: set[str] = set()
            vrt_dir = vrt_file.parent

            for elem in root.iter():
                if elem.tag.lower().endswith("sourcefilename"):
                    txt = (elem.text or "").strip()
                    if not txt:
                        continue
                    rel = elem.attrib.get("relativeToVRT", "0") == "1"
                    ref_path = (vrt_dir / txt) if rel else Path(txt)
                    refs.add(norm_path(str(ref_path)))
            return refs

        conflicts: list[tuple[str, str, str]] = []

        for lyr in self._project().mapLayers().values():
            if not isinstance(lyr, QgsRasterLayer):
                continue

            try:
                src_raw = lyr.source() or ""
            except Exception:
                continue

            src_main = src_raw.split("|", 1)[0].strip()
            src_norm = norm_path(src_main)

            # 1) Direkter Konflikt
            if src_norm in targets_norm:
                conflicts.append((lyr.name(), src_main, "direct"))
                continue

            # 2) Indirekter Konflikt: geladenes VRT referenziert Ziel-Tiles/Ziel-VRT
            if src_main.lower().endswith(".vrt"):
                refs = parse_vrt_references(src_main)
                if refs and (refs & targets_norm):
                    conflicts.append((lyr.name(), src_main, "vrt-references-targets"))

        return conflicts

    def _confirm_export(self, params: dict, export_params: ExportParams) -> bool:
        """Show a pre-export summary and ask for confirmation."""
        layer = params.get("layer")
        layer_name = getattr(layer, "name", lambda: "")() if layer else ""
        render_crs = export_params.render_crs
        output_crs = export_params.output_crs
        render_authid = render_crs.authid() if render_crs and render_crs.isValid() else ""
        output_authid = output_crs.authid() if output_crs and output_crs.isValid() else ""
        requested_crs = params.get("output_crs")
        requested_authid = (
            requested_crs.authid() if requested_crs and requested_crs.isValid() else ""
        )

        lines = [
            self.tr("Layer: {name}").format(name=layer_name),
            self.tr("Output: {path}").format(path=export_params.output_path),
            self.tr("Render CRS: {crs}").format(crs=render_authid),
            self.tr("Raster CRS: {crs}").format(crs=output_authid),
            self.tr("Size: {w} × {h} px @ GSD {gsd}").format(
                w=export_params.width_px,
                h=export_params.height_px,
                gsd=export_params.gsd_m_per_px,
            ),
        ]
        if requested_authid and requested_authid != output_authid:
            lines.append(
                self.tr(
                    "Requested output CRS {requested} is not metric; export falls back to {actual}."
                ).format(requested=requested_authid, actual=output_authid)
            )
        elif render_authid and output_authid and render_authid != output_authid:
            lines.append(
                self.tr(
                    "Rendering is performed in {render} and the final raster is reprojected to {output}."
                ).format(render=render_authid, output=output_authid)
            )
        if export_params.target_scale_denominator is not None:
            lines.append(
                self.tr("Target scale: 1:{scale:.0f}").format(
                    scale=export_params.target_scale_denominator
                )
            )
        if export_params.extent is not None:
            ext = export_params.extent
            lines.append(
                self.tr("Extent (project CRS): W/E/S/N = {w}/{e}/{s}/{n}").format(
                    w=ext.west, e=ext.east, s=ext.south, n=ext.north
                )
            )

        if export_params.create_vrt:
            mode = self.tr("Mode: VRT tiling (no merged raster)")
        else:
            mode = self.tr("Mode: Single raster")
        lines.append(mode)

        settings = QSettings()
        base = "CustomMapDownloader/"
        ask_confirm = settings.value(base + "confirm_export", True, type=bool)
        if ask_confirm is False:
            return True

        msg_box = QMessageBox(
            QMessageBox.Question,
            self.tr("Confirm export"),
            "\n".join(lines),
            QMessageBox.Yes | QMessageBox.No,
            self.iface.mainWindow(),
        )
        msg_box.setDefaultButton(QMessageBox.Yes)

        dont_ask_cb = QCheckBox(self.tr("Do not ask again"))
        msg_box.setCheckBox(dont_ask_cb)

        reply = msg_box.exec_()
        if dont_ask_cb.isChecked():
            settings.setValue(base + "confirm_export", False)

        return reply == QMessageBox.Yes


PROGRESS_TEMPLATES = {
    "STEP_VALIDATE": "{step}/{total}: Validating parameters",
    "STEP_PREPARE": "{step}/{total}: Preparing extent/CRS",
    "STEP_RENDER": "{step}/{total}: Rendering",
    "STEP_WRITE_TIFF": "{step}/{total}: Writing TIFF",
    "STEP_WRITE_GEOTIFF": "{step}/{total}: Writing GeoTIFF",
    "STEP_WRITE_RASTER": "{step}/{total}: Writing raster",
    "STEP_BUILD_VRT": "{step}/{total}: Building VRT",
    "STEP_REPROJECT": "{step}/{total}: Reprojecting output raster",
    "STEP_DONE": "{step}/{total}: Finished",
}
