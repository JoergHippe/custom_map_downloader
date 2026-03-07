# n CustomMapDownloader/core/exporter.py
# -*- coding: utf-8 -*-

"""Exporter implementation (UI-agnostic).

Improvements:
- Cancel support (CancelToken)
- Deterministic progress callback
- QImage->numpy via frombuffer; in tiled mode: defensive copy to avoid access violations on some setups
- BIGTIFF=IF_SAFER + robust GTiff options

Notes:
- Extent policy supports two modes:
  - Preferred: explicit extent (west/east/south/north)
  - Fallback: center (easting/northing) + gsd_m_per_px + width/height
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from osgeo import gdal
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapLayer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsUnitTypes,
)
from qgis.PyQt.QtCore import QCoreApplication, QSize
from qgis.PyQt.QtGui import QColor

from .constants import (
    DEFAULT_MAX_TILE_PX,
    DEFAULT_METRIC_RENDER_CRS_AUTHID,
    LARGE_EXPORT_WARN_RAW_BYTES,
    LARGE_RASTER_STRONG_MAX_DIM_PX,
    LARGE_RASTER_STRONG_TOTAL_PX,
)
from .errors import CancelledError, ExportError, ValidationError
from .export_logging import log_event, summarize_params
from .gdal_io import (
    create_dataset,
    crs_to_wkt,
    driver_for_output,
    gdal_create_options,
    rgba_to_rgb_on_white,
    tile_extension_for,
    worldfile_extension_for,
    write_prj_file,
    write_sidecars,
    write_world_file,
)
from .models import CancelToken, ExportParams
from .raster_ops import (
    build_geotransform,
    ensure_not_fully_transparent,
    qimage_to_rgba_array,
    warp_rendered_raster,
    write_full_raster,
)
from .rendering import (
    layer_extent_in_render_crs,
    render_tile_rgba,
    render_tile_with_retry,
    wait_with_events,
)
from .tiling import build_tile_specs, pad_extent_to_full_tiles, pick_tile_size
from .validation import (
    validate_gsd,
    validate_output_path,
)

ProgressCallback = Callable[[int, str, dict[str, Any]], None]


class GeoTiffExporter:
    """Render a layer and export to TIFF/GeoTIFF."""

    MAX_TILE_PX = DEFAULT_MAX_TILE_PX

    def export(
        self,
        params: ExportParams,
        *,
        progress_cb: Optional[ProgressCallback] = None,
        cancel_token: Optional[CancelToken] = None,
    ) -> str:
        """Export the map to a TIFF/GeoTIFF file.

        Args:
            params: Export parameters.
            progress_cb: Callback(percent, message_key, message_args).
            cancel_token: Shared cancel token from UI.

        Returns:
            Output path.

        Raises:
            ValidationError: On invalid parameters.
            CancelledError: If cancelled by user.
            ExportError: On export failure.
        """
        self._report(progress_cb, 2, "STEP_VALIDATE", {"step": 1, "total": 6})
        self._validate(params)
        self._check_cancel(cancel_token)

        output_path = params.output_path

        self._report(progress_cb, 8, "STEP_PREPARE", {"step": 2, "total": 6})
        render_crs = params.render_crs or self._default_render_crs()
        output_crs = params.output_crs or render_crs
        log_event(
            "export_start", **summarize_params(params, render_crs=render_crs, output_crs=output_crs)
        )

        # Policy: gsd_m_per_px is meters per pixel -> render CRS must use meters.
        if not self._crs_uses_meters(render_crs):
            raise ValidationError(
                "ERR_VALIDATION_RENDER_CRS_UNITS",
                f"Render CRS map units are not meters: {QgsUnitTypes.toString(render_crs.mapUnits())}",
            )

        extent = self._resolve_extent(params, render_crs=render_crs)

        if params.create_vrt and self._crs_differs(render_crs, output_crs):
            raise ValidationError(
                "ERR_VALIDATION_VRT_OUTPUT_CRS_UNSUPPORTED",
                "VRT export currently requires render CRS and output CRS to be identical.",
            )

        if self._crs_differs(render_crs, output_crs):
            with tempfile.TemporaryDirectory(prefix="cmd_render_") as tmp_dir:
                render_output = str(Path(tmp_dir) / "rendered_intermediate.tif")
                render_params = replace(
                    params,
                    output_path=render_output,
                    output_crs=render_crs,
                    create_vrt=False,
                )
                rendered_path = self._export_internal(
                    render_params,
                    render_crs=render_crs,
                    output_crs=render_crs,
                    progress_cb=progress_cb,
                    cancel_token=cancel_token,
                    report_done=False,
                    write_sidecars=False,
                )
                self._check_cancel(cancel_token)
                self._report(progress_cb, 92, "STEP_REPROJECT", {"step": 5, "total": 6})
                result = self._warp_rendered_raster(
                    rendered_path,
                    final_output_path=output_path,
                    render_extent=extent,
                    render_crs=render_crs,
                    output_crs=output_crs,
                    progress_cb=progress_cb,
                    cancel_token=cancel_token,
                )
                log_event("export_success", output_path=result, mode="warp")
                return result

        result = self._export_internal(
            params,
            render_crs=render_crs,
            output_crs=output_crs,
            progress_cb=progress_cb,
            cancel_token=cancel_token,
            report_done=True,
            write_sidecars=True,
        )
        log_event("export_success", output_path=result, mode="direct")
        return result

    def _export_internal(
        self,
        params: ExportParams,
        *,
        render_crs: QgsCoordinateReferenceSystem,
        output_crs: QgsCoordinateReferenceSystem,
        progress_cb: Optional[ProgressCallback],
        cancel_token: Optional[CancelToken],
        report_done: bool,
        write_sidecars: bool,
    ) -> str:
        """Run the export assuming render/output CRS handling is already decided."""
        layer = params.layer
        width = int(params.width_px)
        height = int(params.height_px)
        output_path = params.output_path
        extent = self._resolve_extent(params, render_crs=render_crs)

        tile_w_px, tile_h_px = self._pick_tile_size(params)

        if params.create_vrt:
            extent, width, height = pad_extent_to_full_tiles(
                extent,
                width_px=width,
                height_px=height,
                tile_width_px=tile_w_px,
                tile_height_px=tile_h_px,
            )

        use_tiling = params.create_vrt or (width > tile_w_px) or (height > tile_h_px)
        log_event(
            "export_mode",
            create_vrt=bool(params.create_vrt),
            use_tiling=bool(use_tiling),
            width_px=width,
            height_px=height,
            tile_width_px=tile_w_px,
            tile_height_px=tile_h_px,
        )
        if use_tiling:
            # UI-Logik: "Create VRT" bedeutet VRT-only (Tiles + .vrt), kein Merge in ein großes GeoTIFF.
            if params.create_vrt:
                return self._export_tiled_vrt(
                    params,
                    extent=extent,
                    render_crs=render_crs,
                    output_crs=output_crs,
                    progress_cb=progress_cb,
                    cancel_token=cancel_token,
                    tile_w_px=tile_w_px,
                    tile_h_px=tile_h_px,
                    width_px=width,
                    height_px=height,
                    report_done=report_done,
                    write_sidecars=write_sidecars,
                )

            # Fallback: klassisches, windowed Schreiben in ein einzelnes GeoTIFF.
            return self._export_tiled(
                params,
                extent=extent,
                render_crs=render_crs,
                output_crs=output_crs,
                progress_cb=progress_cb,
                cancel_token=cancel_token,
                tile_size_px=max(tile_w_px, tile_h_px),
                report_done=report_done,
                write_sidecars=write_sidecars,
            )

        raw_bytes = self.estimate_raw_bytes(width, height, bands=4)
        if raw_bytes >= LARGE_EXPORT_WARN_RAW_BYTES:
            self._report(progress_cb, 10, "WARN_LARGE_EXPORT", {"bytes": raw_bytes})

        self._check_cancel(cancel_token)

        map_settings = QgsMapSettings()
        map_settings.setBackgroundColor(QColor(255, 255, 255))
        map_settings.setLayers([layer])
        map_settings.setExtent(extent)
        map_settings.setOutputSize(QSize(width, height))
        map_settings.setDestinationCrs(render_crs)
        if params.output_dpi and params.output_dpi > 0:
            map_settings.setOutputDpi(float(params.output_dpi))

        self._report(progress_cb, 35, "STEP_RENDER", {"step": 3, "total": 6})
        render = QgsMapRendererParallelJob(map_settings)
        render.start()

        while render.isActive():
            self._check_cancel(cancel_token, render_job=render)
            QCoreApplication.processEvents()

        render.waitForFinished()
        rendered_image = render.renderedImage()
        self._check_cancel(cancel_token)

        # ------------------------------------------------------------------
        # Write raster (GeoTIFF/PNG/JPEG) + sidecars (worldfile + .prj)
        # ------------------------------------------------------------------
        self._report(progress_cb, 70, "STEP_WRITE_RASTER", {"step": 4, "total": 6})

        arr_rgba = qimage_to_rgba_array(rendered_image, width=width, height=height)
        ensure_not_fully_transparent(arr_rgba, height=height, width=width)
        geotransform = build_geotransform(extent, width=width, height=height)

        driver_name = self._driver_for_output(output_path)

        # JPEG cannot store alpha; composite to white background and write RGB.
        if driver_name == "JPEG":
            arr = self._rgba_to_rgb_on_white(arr_rgba)
        elif driver_name == "PNG":
            arr = arr_rgba
        else:
            # Default GeoTIFF/GTiff
            arr = arr_rgba

        write_full_raster(
            output_path=output_path,
            arr=arr,
            geotransform=geotransform,
            output_crs=output_crs,
            driver_name=driver_name,
            gdal_create_options=self._gdal_create_options,
            gdal_create_dataset=self._gdal_create_dataset,
            crs_to_wkt=self._crs_to_wkt,
            check_cancel=self._check_cancel,
            cancel_token=cancel_token,
        )

        if write_sidecars:
            self._write_sidecars(output_path, geotransform, output_crs)

        if report_done:
            self._report(progress_cb, 100, "STEP_DONE", {"step": 6, "total": 6})
        return output_path

    @staticmethod
    def estimate_raw_bytes(width_px: int, height_px: int, *, bands: int) -> int:
        """Estimate raw in-memory bytes for the raster array."""
        return int(width_px) * int(height_px) * int(bands)

    def _validate(self, params: ExportParams) -> None:
        """Validate user input and parameters.

        Raises:
            ValidationError: If any parameter is invalid.
        """
        validate_output_path(params.output_path)

        if params.layer is None:
            raise ValidationError("ERR_VALIDATION_LAYER_MISSING", "No layer provided.")
        if params.width_px <= 0 or params.height_px <= 0:
            raise ValidationError(
                "ERR_VALIDATION_SIZE_INVALID",
                f"Invalid size: {params.width_px}x{params.height_px}",
            )

        if (
            params.width_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
            or params.height_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
            or (params.width_px * params.height_px) >= LARGE_RASTER_STRONG_TOTAL_PX
        ):
            raise ValidationError(
                "ERR_VALIDATION_SIZE_TOO_LARGE",
                (
                    f"Raster size too large: {params.width_px}x{params.height_px} px "
                    f"(total {params.width_px * params.height_px:,} px)"
                ),
            )

        validate_gsd(params.gsd_m_per_px)

        # Preferred: explicit extent
        ext = params.extent
        if ext is not None:
            if ext.east <= ext.west or ext.north <= ext.south:
                raise ValidationError(
                    "ERR_VALIDATION_EXTENT_INVALID",
                    f"Invalid extent: W/E/S/N={ext.west}/{ext.east}/{ext.south}/{ext.north}",
                )
            return

        # Fallback: center + GSD
        if params.center is None:
            raise ValidationError("ERR_VALIDATION_CENTER_MISSING", "No center provided.")

    def _default_render_crs(self) -> QgsCoordinateReferenceSystem:
        """Policy:
        - If project CRS uses meters -> use it.
        - Else -> EPSG:3857 (safe default for m/px workflows).
        """
        project = QgsProject.instance()
        if project is None:
            return QgsCoordinateReferenceSystem(DEFAULT_METRIC_RENDER_CRS_AUTHID)
        project_crs = project.crs()
        if project_crs.isValid() and self._crs_uses_meters(project_crs):
            return project_crs
        return QgsCoordinateReferenceSystem(DEFAULT_METRIC_RENDER_CRS_AUTHID)

    def _resolve_extent(
        self, params: ExportParams, *, render_crs: QgsCoordinateReferenceSystem
    ) -> QgsRectangle:
        """Resolve the export extent in render CRS.

        If ``params.extent`` is set, it is transformed to ``render_crs`` (bounding box).
        Otherwise the extent is computed from center (easting/northing) + GSD + pixel size.

        Args:
            params: Export parameters.
            render_crs: CRS used for rendering (typically meters).

        Returns:
            Extent rectangle in ``render_crs``.

        Raises:
            ValidationError: If extent/center values are missing or invalid.
        """
        ext = params.extent
        if ext is not None:
            rect = QgsRectangle(ext.west, ext.south, ext.east, ext.north)
            if rect.width() <= 0 or rect.height() <= 0:
                raise ValidationError(
                    "ERR_VALIDATION_EXTENT_INVALID",
                    f"Invalid extent: W/E/S/N={ext.west}/{ext.east}/{ext.south}/{ext.north}",
                )

            src_crs = ext.crs
            if (
                src_crs is not None
                and src_crs.isValid()
                and render_crs.isValid()
                and src_crs != render_crs
            ):
                try:
                    tr = QgsCoordinateTransform(src_crs, render_crs, QgsProject.instance())
                    rect = tr.transformBoundingBox(rect)
                except Exception as ex:
                    raise ValidationError("ERR_VALIDATION_EXTENT_TRANSFORM_FAILED", str(ex)) from ex

            return rect

        center = params.center
        if center is None:
            raise ValidationError("ERR_VALIDATION_CENTER_MISSING", "No center provided.")

        width = int(params.width_px)
        height = int(params.height_px)
        gsd = float(params.gsd_m_per_px)

        try:
            tr = QgsCoordinateTransform(center.crs, render_crs, QgsProject.instance())
            c = tr.transform(QgsPointXY(center.easting, center.northing))
        except Exception as ex:
            raise ValidationError("ERR_VALIDATION_CENTER_TRANSFORM_FAILED", str(ex)) from ex

        half_width = (width * gsd) / 2.0
        half_height = (height * gsd) / 2.0
        return QgsRectangle(
            c.x() - half_width,
            c.y() - half_height,
            c.x() + half_width,
            c.y() + half_height,
        )

    def _crs_uses_meters(self, crs: QgsCoordinateReferenceSystem) -> bool:
        try:
            return crs.mapUnits() == Qgis.DistanceUnit.Meters
        except Exception:
            return QgsUnitTypes.toString(crs.mapUnits()).lower().startswith("meter")

    def _crs_to_wkt(self, crs: QgsCoordinateReferenceSystem) -> str:
        return crs_to_wkt(crs)

    def _check_cancel(
        self,
        token: Optional[CancelToken],
        *,
        render_job: Optional[QgsMapRendererParallelJob] = None,
    ) -> None:
        if token is not None and token.cancelled:
            if render_job is not None:
                try:
                    if hasattr(render_job, "cancelWithoutBlocking"):
                        render_job.cancelWithoutBlocking()
                    else:
                        render_job.cancel()
                except Exception:
                    pass
            raise CancelledError("ERR_CANCELLED", "Cancelled by user.")

    def _report(
        self,
        cb: Optional[ProgressCallback],
        percent: int,
        key: str,
        args: Optional[dict[str, Any]] = None,
    ) -> None:
        if cb is not None:
            cb(int(percent), key, args or {})

    def _pick_tile_size(self, params: ExportParams) -> tuple[int, int]:
        return pick_tile_size(params, default_max_tile_px=self.MAX_TILE_PX)

    def _crs_differs(
        self,
        left: QgsCoordinateReferenceSystem,
        right: QgsCoordinateReferenceSystem,
    ) -> bool:
        """Return True if two valid CRS objects are semantically different."""
        if not left.isValid() or not right.isValid():
            return False
        return left != right

    def _transform_extent_rect(
        self,
        rect: QgsRectangle,
        *,
        src_crs: QgsCoordinateReferenceSystem,
        dst_crs: QgsCoordinateReferenceSystem,
    ) -> QgsRectangle:
        """Transform a rectangle bounding box into another CRS."""
        if not self._crs_differs(src_crs, dst_crs):
            return QgsRectangle(
                rect.xMinimum(),
                rect.yMinimum(),
                rect.xMaximum(),
                rect.yMaximum(),
            )
        try:
            transform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
            return transform.transformBoundingBox(rect)
        except Exception as ex:
            raise ExportError("ERR_WARP_FAILED", f"Failed to transform output extent: {ex}") from ex

    def _export_tiled_vrt(
        self,
        params: ExportParams,
        *,
        extent: QgsRectangle,
        render_crs: QgsCoordinateReferenceSystem,
        output_crs: QgsCoordinateReferenceSystem,
        progress_cb: Optional[ProgressCallback],
        cancel_token: Optional[CancelToken],
        tile_w_px: int,
        tile_h_px: int,
        width_px: int,
        height_px: int,
        report_done: bool,
        write_sidecars: bool,
    ) -> str:
        """Export as VRT-only: write georeferenced tiles and build a VRT mosaic.

        Requirements:
            - Tiles are written into the same folder as ``params.output_path``.
            - No dedicated tiles subfolder.
            - No merged "big" raster is written.
            - VRT references tiles via relative paths.
            - Tile format follows the user-selected output format (tif/png/jpg).
              (JPEG: alpha is composited onto white.)
            - For PNG/JPEG, write worldfile + .prj (per tile).
              For TIFF, also write worldfile + .prj (harmless, keeps behavior consistent).
        """
        layer = params.layer
        width = int(width_px)
        height = int(height_px)

        out_path = Path(params.output_path)
        out_dir = out_path.parent
        base = out_path.with_suffix("")  # remove extension (even if .tif/.png/.jpg)
        vrt_path = base.with_suffix(".vrt")

        # Tile format derives from selected output_path extension.
        tile_ext = self._tile_extension_for(str(out_path))  # ".tif" / ".png" / ".jpg"

        px_w = extent.width() / float(width)
        px_h = extent.height() / float(height)
        tile_specs = build_tile_specs(
            extent,
            width_px=width,
            height_px=height,
            tile_width_px=tile_w_px,
            tile_height_px=tile_h_px,
            base_percent=15,
            span_percent=75,
        )
        total_tiles = len(tile_specs)
        layer_extent_render = layer_extent_in_render_crs(layer, render_crs=render_crs)
        rate_limit_s = 0.05

        tile_paths_abs: list[str] = []
        blank_tiles = 0

        self._report(progress_cb, 15, "STEP_RENDER", {"step": 3, "total": 6})

        for tile in tile_specs:
            self._check_cancel(cancel_token)
            arr, was_blank = render_tile_with_retry(
                tile=tile,
                layer=layer,
                render_crs=render_crs,
                output_dpi=params.output_dpi,
                cancel_token=cancel_token,
                layer_extent_render=layer_extent_render,
                progress_cb=progress_cb,
                report=self._report,
                wait_fn=self._wait_with_events,
                render_fn=self._render_tile_rgba,
                check_cancel=self._check_cancel,
            )

            if was_blank:
                blank_tiles += 1

            tile_name = f"{base.name}__tile_r{tile.row:03d}_c{tile.col:03d}{tile_ext}"
            tile_path = out_dir / tile_name

            driver_name = self._driver_for_output(str(tile_path))
            driver = gdal.GetDriverByName(driver_name)
            if driver is None:
                raise ExportError(
                    "ERR_GDAL_DRIVER_MISSING", f"GDAL driver not found: {driver_name}"
                )

            if driver_name == "JPEG":
                write_arr = self._rgba_to_rgb_on_white(arr)
                bands = 3
            elif driver_name == "PNG":
                write_arr = arr
                bands = 4
            else:
                write_arr = arr
                bands = 4

            ds = driver.Create(
                str(tile_path),
                tile.width_px,
                tile.height_px,
                bands,
                gdal.GDT_Byte,
                options=self._gdal_create_options(driver_name),
            )
            if ds is None:
                raise ExportError("ERR_GDAL_CREATE_FAILED", f"Failed to create tile: {tile_path}")

            try:
                tile_gt = [
                    tile.extent.xMinimum(),
                    px_w,
                    0.0,
                    tile.extent.yMaximum(),
                    0.0,
                    -px_h,
                ]
                ds.SetGeoTransform(tile_gt)
                ds.SetProjection(self._crs_to_wkt(output_crs))

                for i in range(bands):
                    band = ds.GetRasterBand(i + 1)
                    band.WriteArray(write_arr[:, :, i])
                    band.FlushCache()
            finally:
                ds = None

            if write_sidecars:
                self._write_sidecars(str(tile_path), tile_gt, output_crs)

            tile_paths_abs.append(str(tile_path))
            self._wait_with_events(rate_limit_s, cancel_token=cancel_token)
            self._report(
                progress_cb,
                tile.percent,
                "STEP_WRITE_RASTER",
                {"step": 4, "total": 6},
            )

        if blank_tiles == total_tiles:
            raise ExportError(
                "ERR_RENDER_EMPTY",
                "All tiles rendered fully transparent. Likely service limits/timeouts/throttling.",
            )

        self._check_cancel(cancel_token)
        self._report(progress_cb, 92, "STEP_BUILD_VRT", {"step": 5, "total": 6})

        vrt_ds = gdal.BuildVRT(str(vrt_path), tile_paths_abs)
        if vrt_ds is None:
            raise ExportError("ERR_VRT_BUILD_FAILED", "gdal.BuildVRT returned None")
        vrt_ds = None

        # Make VRT portable (relative SourceFilename entries)
        try:
            self._make_vrt_paths_relative(vrt_path, tile_paths_abs)
        except Exception as ex:
            log_event(
                "vrt_relative_paths_warning",
                output_path=str(vrt_path),
                details=str(ex),
            )
            self._report(
                progress_cb,
                96,
                "WARN_VRT_ABSOLUTE_PATHS",
                {"details": str(ex)},
            )

        if report_done:
            self._report(progress_cb, 100, "STEP_DONE", {"step": 6, "total": 6})
        return str(vrt_path)

    def _make_vrt_paths_relative(self, vrt_path: Path, tile_paths_abs: list[str]) -> None:
        """Rewrite VRT SourceFilename entries to be relative to the VRT.

        Rationale:
            The Python GDAL bindings used by QGIS on Windows don't reliably expose
            the "-relative" flag from gdalbuildvrt. Post-processing the XML is a
            pragmatic way to make the VRT portable.
        """
        text = vrt_path.read_text(encoding="utf-8", errors="replace")

        # Replace known absolute paths by their basenames and mark relativeToVRT="1".
        for p in tile_paths_abs:
            base_name = os.path.basename(p)
            # Handle both Windows backslashes and normalized paths.
            escaped = re.escape(p)
            escaped2 = re.escape(p.replace("\\", "/"))

            text = re.sub(
                rf"(<SourceFilename[^>]*>)\s*{escaped}\s*(</SourceFilename>)",
                rf"\1{base_name}\2",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                rf"(<SourceFilename[^>]*>)\s*{escaped2}\s*(</SourceFilename>)",
                rf"\1{base_name}\2",
                text,
                flags=re.IGNORECASE,
            )

        # Ensure relativeToVRT="1" where possible.
        text = re.sub(
            r"<SourceFilename(\s+[^>]*?)relativeToVRT=\"0\"",
            r"<SourceFilename\1relativeToVRT=\"1\"",
            text,
            flags=re.IGNORECASE,
        )

        vrt_path.write_text(text, encoding="utf-8")

    def _export_tiled(
        self,
        params: ExportParams,
        *,
        extent: QgsRectangle,
        render_crs: QgsCoordinateReferenceSystem,
        output_crs: QgsCoordinateReferenceSystem,
        progress_cb: Optional[ProgressCallback],
        cancel_token: Optional[CancelToken],
        tile_size_px: int,
        report_done: bool,
        write_sidecars: bool,
    ) -> str:
        """Export using tiled rendering and windowed writes to one output raster.

        Notes:
            - Output format follows params.output_path extension (tif/png/jpg).
            - JPEG has no alpha: RGBA tiles are composited onto white and written as RGB.
            - Sidecars:
                - Always write worldfile + .prj (PNG/JPEG required; TIFF harmless).
            - For non-GTiff drivers, windowed writes are still attempted; if the chosen driver
              does not support it properly in a given GDAL build, you may need to fall back
              to building the full image and writing once. (Most QGIS/GDAL builds handle this.)
        """
        layer = params.layer
        width = int(params.width_px)
        height = int(params.height_px)
        output_path = params.output_path

        px_w = extent.width() / float(width)
        px_h = extent.height() / float(height)

        tile_specs = build_tile_specs(
            extent,
            width_px=width,
            height_px=height,
            tile_width_px=tile_size_px,
            tile_height_px=tile_size_px,
            base_percent=15,
            span_percent=80,
        )
        total_tiles = len(tile_specs)
        blank_tiles = 0
        layer_extent_render = layer_extent_in_render_crs(layer, render_crs=render_crs)

        geotransform = [
            extent.xMinimum(),
            px_w,
            0.0,
            extent.yMaximum(),
            0.0,
            -px_h,
        ]

        driver_name = self._driver_for_output(output_path)
        driver = gdal.GetDriverByName(driver_name)
        if driver is None:
            raise ExportError("ERR_GDAL_DRIVER_MISSING", f"GDAL driver not found: {driver_name}")

        # Choose bands based on output format
        out_bands = 3 if driver_name == "JPEG" else 4

        dataset = driver.Create(
            output_path,
            width,
            height,
            out_bands,
            gdal.GDT_Byte,
            options=self._gdal_create_options(driver_name),
        )
        if dataset is None:
            raise ExportError("ERR_GDAL_CREATE_FAILED", "driver.Create returned None.")

        try:
            dataset.SetGeoTransform(geotransform)
            dataset.SetProjection(self._crs_to_wkt(output_crs))

            rate_limit_s = 0.05

            self._report(progress_cb, 15, "STEP_RENDER", {"step": 3, "total": 6})

            for tile in tile_specs:
                self._check_cancel(cancel_token)
                arr, was_blank = render_tile_with_retry(
                    tile=tile,
                    layer=layer,
                    render_crs=render_crs,
                    output_dpi=params.output_dpi,
                    cancel_token=cancel_token,
                    layer_extent_render=layer_extent_render,
                    progress_cb=progress_cb,
                    report=self._report,
                    wait_fn=self._wait_with_events,
                    render_fn=self._render_tile_rgba,
                    check_cancel=self._check_cancel,
                )

                if was_blank:
                    blank_tiles += 1

                if driver_name == "JPEG":
                    write_arr = self._rgba_to_rgb_on_white(arr)
                    write_bands = 3
                else:
                    write_arr = arr
                    write_bands = 4

                self._wait_with_events(rate_limit_s, cancel_token=cancel_token)

                for i in range(write_bands):
                    band = dataset.GetRasterBand(i + 1)
                    band.WriteArray(write_arr[:, :, i], xoff=tile.xoff, yoff=tile.yoff)

                self._report(
                    progress_cb,
                    tile.percent,
                    "STEP_WRITE_RASTER",
                    {"step": 4, "total": 6},
                )

            dataset.FlushCache()

        finally:
            dataset = None

        # Sidecars (always; PNG/JPEG required)
        if write_sidecars:
            self._write_sidecars(output_path, geotransform, output_crs)

        if blank_tiles == total_tiles:
            raise ExportError(
                "ERR_RENDER_EMPTY",
                "All tiles rendered fully transparent. Likely service limits/timeouts/throttling.",
            )

        if report_done:
            self._report(progress_cb, 100, "STEP_DONE", {"step": 6, "total": 6})
        return output_path

    def _warp_rendered_raster(
        self,
        source_path: str,
        *,
        final_output_path: str,
        render_extent: QgsRectangle,
        render_crs: QgsCoordinateReferenceSystem,
        output_crs: QgsCoordinateReferenceSystem,
        progress_cb: Optional[ProgressCallback],
        cancel_token: Optional[CancelToken],
    ) -> str:
        return warp_rendered_raster(
            source_path=source_path,
            final_output_path=final_output_path,
            render_extent=render_extent,
            render_crs=render_crs,
            output_crs=output_crs,
            transform_extent_rect=self._transform_extent_rect,
            driver_for_output=self._driver_for_output,
            crs_to_wkt=self._crs_to_wkt,
            gdal_create_options=self._gdal_create_options,
            write_sidecars=self._write_sidecars,
            report=self._report,
            progress_cb=progress_cb,
            check_cancel=self._check_cancel,
            cancel_token=cancel_token,
        )

    def _render_tile_rgba(
        self,
        *,
        layer: QgsMapLayer,
        tile_extent: QgsRectangle,
        render_crs: QgsCoordinateReferenceSystem,
        width_px: int,
        height_px: int,
        output_dpi: Optional[float],
        cancel_token: Optional[CancelToken],
    ) -> np.ndarray:
        return render_tile_rgba(
            layer=layer,
            tile_extent=tile_extent,
            render_crs=render_crs,
            width_px=width_px,
            height_px=height_px,
            output_dpi=output_dpi,
            cancel_token=cancel_token,
            check_cancel=self._check_cancel,
        )

    def _wait_with_events(
        self,
        seconds: float,
        *,
        cancel_token: Optional[CancelToken],
        render_job: Optional[QgsMapRendererParallelJob] = None,
    ) -> None:
        wait_with_events(
            seconds,
            check_cancel=self._check_cancel,
            cancel_token=cancel_token,
            render_job=render_job,
        )

    def _driver_for_output(self, output_path: str) -> str:
        return driver_for_output(output_path)

    def _tile_extension_for(self, output_path: str) -> str:
        return tile_extension_for(output_path)

    def _gdal_create_options(self, driver_name: str) -> list[str]:
        return gdal_create_options(driver_name)

    def _gdal_create_dataset(
        self,
        *,
        output_path: str,
        driver_name: str,
        width: int,
        height: int,
        bands: int,
        options: list[str],
    ):
        return create_dataset(
            output_path=output_path,
            driver_name=driver_name,
            width=width,
            height=height,
            bands=bands,
            options=options,
        )

    def _rgba_to_rgb_on_white(self, arr_rgba: np.ndarray) -> np.ndarray:
        return rgba_to_rgb_on_white(arr_rgba)

    def _write_prj_file(self, output_path: str, crs: QgsCoordinateReferenceSystem) -> None:
        write_prj_file(output_path, crs)

    def _worldfile_extension_for(self, output_path: str) -> str:
        return worldfile_extension_for(output_path)

    def _write_world_file(self, path: str, geotransform: list[float]) -> None:
        write_world_file(path, geotransform)

    def _write_sidecars(
        self,
        path: str,
        geotransform: list[float],
        crs: QgsCoordinateReferenceSystem,
    ) -> None:
        write_sidecars(path, geotransform, crs)
