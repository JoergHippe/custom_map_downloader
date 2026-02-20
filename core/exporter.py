#n CustomMapDownloader/core/exporter.py
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
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from osgeo import gdal, osr
from qgis.PyQt.QtCore import QCoreApplication, QSize
from qgis.PyQt.QtGui import QColor, QImage
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

from .errors import CancelledError, ExportError, ValidationError
from .models import CancelToken, ExportParams
from .constants import (
    LARGE_RASTER_STRONG_MAX_DIM_PX,
    LARGE_RASTER_STRONG_TOTAL_PX,
)
from .validation import (
    validate_output_path,
    validate_gsd,
)

ProgressCallback = Callable[[int, str, dict[str, Any]], None]


class GeoTiffExporter:
    """Render a layer and export to TIFF/GeoTIFF."""

    MAX_TILE_PX = 2048

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

        layer = params.layer
        width = int(params.width_px)
        height = int(params.height_px)
        output_path = params.output_path

        self._report(progress_cb, 8, "STEP_PREPARE", {"step": 2, "total": 6})
        render_crs = params.render_crs or self._default_render_crs()
        output_crs = params.output_crs or render_crs

        # Policy: gsd_m_per_px is meters per pixel -> render CRS must use meters.
        if not self._crs_uses_meters(render_crs):
            raise ValidationError(
                "ERR_VALIDATION_RENDER_CRS_UNITS",
                f"Render CRS map units are not meters: {QgsUnitTypes.toString(render_crs.mapUnits())}",
            )

        extent = self._resolve_extent(params, render_crs=render_crs)

        tile_w_px, tile_h_px = self._pick_tile_size(params)

        if params.create_vrt:
            # Pixelgröße aus aktuellem Extent ableiten (damit "look & feel" gleich bleibt)
            px_w = extent.width() / float(width)
            px_h = extent.height() / float(height)

            cols = (width + tile_w_px - 1) // tile_w_px
            rows = (height + tile_h_px - 1) // tile_h_px

            new_width = cols * tile_w_px
            new_height = rows * tile_h_px

            dx_px = new_width - width
            dy_px = new_height - height

            # Symmetrisch um die Mitte erweitern
            dx_map = dx_px * px_w
            dy_map = dy_px * px_h

            extent = QgsRectangle(
                extent.xMinimum() - dx_map / 2.0,
                extent.yMinimum() - dy_map / 2.0,
                extent.xMaximum() + dx_map / 2.0,
                extent.yMaximum() + dy_map / 2.0,
            )

            width = new_width
            height = new_height

        use_tiling = params.create_vrt or (width > tile_w_px) or (height > tile_h_px)
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
            )

        raw_bytes = self.estimate_raw_bytes(width, height, bands=4)
        if raw_bytes >= 800 * 1024 * 1024:  # ~800 MB raw RGBA
            self._report(progress_cb, 10, "WARN_LARGE_EXPORT", {"bytes": raw_bytes})

        self._check_cancel(cancel_token)

        map_settings = QgsMapSettings()
        map_settings.setBackgroundColor(QColor(255, 255, 255))
        map_settings.setLayers([layer])
        map_settings.setExtent(extent)
        map_settings.setOutputSize(QSize(width, height))
        map_settings.setDestinationCrs(render_crs)

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

        rendered_image = rendered_image.convertToFormat(QImage.Format_RGBA8888)

        ptr = rendered_image.bits()
        byte_count = (
            rendered_image.sizeInBytes()
            if hasattr(rendered_image, "sizeInBytes")
            else rendered_image.byteCount()
        )
        ptr.setsize(byte_count)
        arr_rgba = np.frombuffer(ptr, dtype=np.uint8).reshape(height, width, 4)

        step_y = max(1, height // 200)
        step_x = max(1, width // 200)
        alpha_sample = arr_rgba[::step_y, ::step_x, 3]
        if int(alpha_sample.max()) == 0:
            raise ExportError(
                "ERR_RENDER_EMPTY",
                "Rendered image is fully transparent. Likely network timeout or service WIDTH/HEIGHT limit. "
                "Try smaller size, higher timeout, or tiling.",
            )

        px_w = extent.width() / float(width)
        px_h = extent.height() / float(height)
        geotransform = [extent.xMinimum(), px_w, 0.0, extent.yMaximum(), 0.0, -px_h]

        driver_name = self._driver_for_output(output_path)

        # JPEG cannot store alpha; composite to white background and write RGB.
        if driver_name == "JPEG":
            arr = self._rgba_to_rgb_on_white(arr_rgba)
            bands = 3
        elif driver_name == "PNG":
            arr = arr_rgba
            bands = 4
        else:
            # Default GeoTIFF/GTiff
            arr = arr_rgba
            bands = 4

        options = self._gdal_create_options(driver_name)

        dataset = self._gdal_create_dataset(
            output_path=output_path,
            driver_name=driver_name,
            width=width,
            height=height,
            bands=bands,
            options=options,
        )
        if dataset is None:
            raise ExportError("ERR_GDAL_CREATE_FAILED", f"driver.Create returned None (driver={driver_name}).")

        try:
            # Some drivers accept geo metadata, some don’t; we set it anyway.
            dataset.SetGeoTransform(geotransform)
            dataset.SetProjection(self._crs_to_wkt(output_crs))

            for i in range(bands):
                self._check_cancel(cancel_token)
                band = dataset.GetRasterBand(i + 1)
                band.WriteArray(arr[:, :, i])
                band.FlushCache()
        finally:
            dataset = None

        # Sidecars: always write worldfile; for PNG/JPEG also write .prj
        self._write_sidecars(output_path, geotransform, output_crs)

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
        project_crs = QgsProject.instance().crs()
        if project_crs.isValid() and self._crs_uses_meters(project_crs):
            return project_crs
        return QgsCoordinateReferenceSystem("EPSG:3857")

    def _resolve_extent(self, params: ExportParams, *, render_crs: QgsCoordinateReferenceSystem) -> QgsRectangle:
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
            if src_crs is not None and src_crs.isValid() and render_crs.isValid() and src_crs != render_crs:
                try:
                    tr = QgsCoordinateTransform(src_crs, render_crs, QgsProject.instance())
                    rect = tr.transformBoundingBox(rect)
                except Exception as ex:
                    raise ValidationError("ERR_VALIDATION_EXTENT_TRANSFORM_FAILED", str(ex))

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
            raise ValidationError("ERR_VALIDATION_CENTER_TRANSFORM_FAILED", str(ex))

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
        if not crs.isValid():
            raise ExportError("ERR_CRS_INVALID", "CRS is not valid.")

        authid = crs.authid() or ""
        m = re.match(r"^EPSG:(\d+)$", authid)
        srs = osr.SpatialReference()

        if m:
            srs.ImportFromEPSG(int(m.group(1)))
            return srs.ExportToWkt()

        wkt = crs.toWkt()
        err = srs.ImportFromWkt(wkt)
        if err != 0:
            raise ExportError(
                "ERR_CRS_TO_WKT_FAILED",
                f"OSR ImportFromWkt failed (code={err}).",
            )
        return srs.ExportToWkt()

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
        """Pick tile width/height from params with sane defaults.

        Policy:
            - Use ``vrt_max_cols`` / ``vrt_max_rows`` if > 0.
            - Else use ``vrt_preset_size`` (UI preset) if > 0.
            - Otherwise fall back to ``MAX_TILE_PX``.
            - Clamp to a reasonable range to avoid tiny tiles.
        """
        preset = int(params.vrt_preset_size or 0)

        tw = int(params.vrt_max_cols or 0)
        th = int(params.vrt_max_rows or 0)

        if tw <= 0 and preset > 0:
            tw = preset
        if th <= 0 and preset > 0:
            th = preset

        if tw <= 0:
            tw = self.MAX_TILE_PX
        if th <= 0:
            th = self.MAX_TILE_PX

        tw = max(64, min(8192, tw))
        th = max(64, min(8192, th))
        return tw, th

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

        cols = (width + tile_w_px - 1) // tile_w_px
        rows = (height + tile_h_px - 1) // tile_h_px
        total_tiles = rows * cols

        # Optional optimization: skip retry escalation if tile doesn't overlap.
        layer_extent_render = None
        try:
            layer_extent = layer.extent()
            if layer.crs().isValid() and render_crs.isValid() and layer.crs() != render_crs:
                tr = QgsCoordinateTransform(layer.crs(), render_crs, QgsProject.instance())
                layer_extent_render = tr.transformBoundingBox(layer_extent)
            else:
                layer_extent_render = layer_extent
        except Exception:
            layer_extent_render = None

        max_retries = 3
        base_backoff_s = 0.7
        max_backoff_s = 8.0
        rate_limit_s = 0.05

        tile_paths_abs: list[str] = []
        blank_tiles = 0

        self._report(progress_cb, 15, "STEP_RENDER", {"step": 3, "total": 6})

        for r in range(rows):
            for c in range(cols):
                self._check_cancel(cancel_token)

                xoff = c * tile_w_px
                yoff = r * tile_h_px
                tw = min(tile_w_px, width - xoff)
                th = min(tile_h_px, height - yoff)

                xmin = extent.xMinimum() + (xoff * px_w)
                xmax = xmin + (tw * px_w)
                ymax = extent.yMaximum() - (yoff * px_h)
                ymin = ymax - (th * px_h)
                tile_extent = QgsRectangle(xmin, ymin, xmax, ymax)

                done = (r * cols) + c + 1
                percent = 15 + int((done / float(total_tiles)) * 75)

                tile_overlaps_layer = True
                if layer_extent_render is not None:
                    try:
                        tile_overlaps_layer = tile_extent.intersects(layer_extent_render)
                    except Exception:
                        tile_overlaps_layer = True

                arr: Optional[np.ndarray] = None
                was_blank = False

                for attempt in range(max_retries + 1):
                    self._check_cancel(cancel_token)

                    try:
                        arr = self._render_tile_rgba(
                            layer=layer,
                            tile_extent=tile_extent,
                            render_crs=render_crs,
                            width_px=tw,
                            height_px=th,
                            cancel_token=cancel_token,
                        )
                    except Exception as ex:
                        if attempt < max_retries:
                            backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
                            backoff *= (0.8 + 0.4 * random.random())
                            self._report(
                                progress_cb,
                                percent,
                                "WARN_TILE_RETRY",
                                {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
                            )
                            self._wait_with_events(backoff, cancel_token=cancel_token)
                            continue
                        raise ExportError("ERR_RENDER_TILE_FAILED", str(ex))

                    # blank check (alpha)
                    sy = max(1, th // 64)
                    sx = max(1, tw // 64)
                    alpha_max = int(arr[::sy, ::sx, 3].max())
                    was_blank = alpha_max == 0

                    if not was_blank:
                        break

                    if attempt < max_retries and tile_overlaps_layer:
                        backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
                        backoff *= (0.8 + 0.4 * random.random())
                        self._report(
                            progress_cb,
                            percent,
                            "WARN_TILE_RETRY",
                            {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
                        )
                        self._wait_with_events(backoff, cancel_token=cancel_token)
                        continue

                    break

                if arr is None:
                    raise ExportError("ERR_RENDER_TILE_FAILED", "Tile render returned no buffer.")

                if was_blank:
                    blank_tiles += 1

                tile_name = f"{base.name}__tile_r{r:03d}_c{c:03d}{tile_ext}"
                tile_path = out_dir / tile_name

                driver_name = self._driver_for_output(str(tile_path))
                driver = gdal.GetDriverByName(driver_name)
                if driver is None:
                    raise ExportError("ERR_GDAL_DRIVER_MISSING", f"GDAL driver not found: {driver_name}")

                # JPEG has no alpha -> composite on white and write RGB.
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
                    tw,
                    th,
                    bands,
                    gdal.GDT_Byte,
                    options=self._gdal_create_options(driver_name),
                )
                if ds is None:
                    raise ExportError("ERR_GDAL_CREATE_FAILED", f"Failed to create tile: {tile_path}")

                try:
                    tile_gt = [xmin, px_w, 0.0, ymax, 0.0, -px_h]
                    ds.SetGeoTransform(tile_gt)
                    ds.SetProjection(self._crs_to_wkt(output_crs))

                    for i in range(bands):
                        band = ds.GetRasterBand(i + 1)
                        band.WriteArray(write_arr[:, :, i])
                        band.FlushCache()
                finally:
                    ds = None

                # Sidecars per tile (always; for PNG/JPEG required)
                self._write_sidecars(str(tile_path), tile_gt, output_crs)

                tile_paths_abs.append(str(tile_path))
                self._wait_with_events(rate_limit_s, cancel_token=cancel_token)
                self._report(progress_cb, percent, "STEP_WRITE_RASTER", {"step": 4, "total": 6})

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
        except Exception:
            pass

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

        cols = (width + tile_size_px - 1) // tile_size_px
        rows = (height + tile_size_px - 1) // tile_size_px
        total_tiles = rows * cols

        blank_tiles = 0

        layer_extent_render = None
        try:
            layer_extent = layer.extent()
            if layer.crs().isValid() and render_crs.isValid() and layer.crs() != render_crs:
                tr = QgsCoordinateTransform(layer.crs(), render_crs, QgsProject.instance())
                layer_extent_render = tr.transformBoundingBox(layer_extent)
            else:
                layer_extent_render = layer_extent
        except Exception:
            layer_extent_render = None

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

            max_retries = 3
            base_backoff_s = 0.7
            max_backoff_s = 8.0
            rate_limit_s = 0.05

            self._report(progress_cb, 15, "STEP_RENDER", {"step": 3, "total": 6})

            for r in range(rows):
                for c in range(cols):
                    self._check_cancel(cancel_token)

                    xoff = c * tile_size_px
                    yoff = r * tile_size_px
                    tw = min(tile_size_px, width - xoff)
                    th = min(tile_size_px, height - yoff)

                    xmin = extent.xMinimum() + (xoff * px_w)
                    xmax = xmin + (tw * px_w)
                    ymax = extent.yMaximum() - (yoff * px_h)
                    ymin = ymax - (th * px_h)
                    tile_extent = QgsRectangle(xmin, ymin, xmax, ymax)

                    done = (r * cols) + c + 1
                    percent = 15 + int((done / float(total_tiles)) * 80)

                    tile_overlaps_layer = True
                    if layer_extent_render is not None:
                        try:
                            tile_overlaps_layer = tile_extent.intersects(layer_extent_render)
                        except Exception:
                            tile_overlaps_layer = True

                    arr: Optional[np.ndarray] = None
                    was_blank = False

                    for attempt in range(max_retries + 1):
                        self._check_cancel(cancel_token)

                        try:
                            arr = self._render_tile_rgba(
                                layer=layer,
                                tile_extent=tile_extent,
                                render_crs=render_crs,
                                width_px=tw,
                                height_px=th,
                                cancel_token=cancel_token,
                            )
                        except Exception as ex:
                            if attempt < max_retries:
                                backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
                                backoff *= (0.8 + 0.4 * random.random())
                                self._report(
                                    progress_cb,
                                    percent,
                                    "WARN_TILE_RETRY",
                                    {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
                                )
                                self._wait_with_events(backoff, cancel_token=cancel_token)
                                continue
                            raise ExportError("ERR_RENDER_TILE_FAILED", str(ex))

                        sy = max(1, th // 64)
                        sx = max(1, tw // 64)
                        alpha_max = int(arr[::sy, ::sx, 3].max())
                        was_blank = alpha_max == 0

                        if not was_blank:
                            break

                        if attempt < max_retries and tile_overlaps_layer:
                            backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
                            backoff *= (0.8 + 0.4 * random.random())
                            self._report(
                                progress_cb,
                                percent,
                                "WARN_TILE_RETRY",
                                {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
                            )
                            self._wait_with_events(backoff, cancel_token=cancel_token)
                            continue

                        break

                    if arr is None:
                        raise ExportError("ERR_RENDER_TILE_FAILED", "Tile render returned no buffer.")

                    if was_blank:
                        blank_tiles += 1

                    # Convert for JPEG if needed
                    if driver_name == "JPEG":
                        write_arr = self._rgba_to_rgb_on_white(arr)  # (th, tw, 3)
                        write_bands = 3
                    else:
                        write_arr = arr  # (th, tw, 4)
                        write_bands = 4

                    self._wait_with_events(rate_limit_s, cancel_token=cancel_token)

                    # Windowed write into the dataset
                    for i in range(write_bands):
                        band = dataset.GetRasterBand(i + 1)
                        band.WriteArray(write_arr[:, :, i], xoff=xoff, yoff=yoff)

                    self._report(progress_cb, percent, "STEP_WRITE_RASTER", {"step": 4, "total": 6})

            dataset.FlushCache()

        finally:
            dataset = None

        # Sidecars (always; PNG/JPEG required)
        self._write_sidecars(output_path, geotransform, output_crs)

        if blank_tiles == total_tiles:
            raise ExportError(
                "ERR_RENDER_EMPTY",
                "All tiles rendered fully transparent. Likely service limits/timeouts/throttling.",
            )

        self._report(progress_cb, 100, "STEP_DONE", {"step": 6, "total": 6})
        return output_path

    def _render_tile_rgba(
        self,
        *,
        layer: QgsMapLayer,
        tile_extent: QgsRectangle,
        render_crs: QgsCoordinateReferenceSystem,
        width_px: int,
        height_px: int,
        cancel_token: Optional[CancelToken],
    ) -> np.ndarray:
        """Render one tile into a detached RGBA array (height_px, width_px, 4)."""
        map_settings = QgsMapSettings()
        map_settings.setBackgroundColor(QColor(255, 255, 255))
        map_settings.setLayers([layer])
        map_settings.setExtent(tile_extent)
        map_settings.setOutputSize(QSize(width_px, height_px))
        map_settings.setDestinationCrs(render_crs)

        job = QgsMapRendererParallelJob(map_settings)
        job.start()

        while job.isActive():
            self._check_cancel(cancel_token, render_job=job)
            QCoreApplication.processEvents()

        job.waitForFinished()

        img = job.renderedImage().convertToFormat(QImage.Format_RGBA8888)
        ptr = img.bits()
        byte_count = img.sizeInBytes() if hasattr(img, "sizeInBytes") else img.byteCount()
        ptr.setsize(byte_count)

        buf = np.frombuffer(ptr, dtype=np.uint8).copy()
        return buf.reshape(height_px, width_px, 4)

    def _wait_with_events(
        self,
        seconds: float,
        *,
        cancel_token: Optional[CancelToken],
        render_job: Optional[QgsMapRendererParallelJob] = None,
    ) -> None:
        """Wait while keeping the UI responsive and honoring cancellation."""
        end_t = time.monotonic() + max(0.0, float(seconds))
        while time.monotonic() < end_t:
            self._check_cancel(cancel_token, render_job=render_job)
            QCoreApplication.processEvents()
            time.sleep(0.05)

    def _driver_for_output(self, output_path: str) -> str:
        """Return GDAL driver name for the given output path suffix."""
        ext = (Path(output_path).suffix or "").lower()
        if ext in {".tif", ".tiff"}:
            return "GTiff"
        if ext == ".png":
            return "PNG"
        if ext in {".jpg", ".jpeg"}:
            return "JPEG"
        return "GTiff"

    def _tile_extension_for(self, output_path: str) -> str:
        """Normalize raster extension used for tiles (and single export)."""
        ext = (Path(output_path).suffix or "").lower()
        if ext == ".tiff":
            return ".tif"
        if ext == ".jpeg":
            return ".jpg"
        if ext in {".tif", ".png", ".jpg"}:
            return ext
        # If someone passes a .vrt as output_path, default tiles to GeoTIFF.
        if ext == ".vrt":
            return ".tif"
        return ".tif"

    def _gdal_create_options(self, driver_name: str) -> list[str]:
        """Return GDAL Create() options per driver."""
        if driver_name == "GTiff":
            return ["COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_SAFER"]
        if driver_name == "JPEG":
            # Good default. You can expose this later as a UI option.
            return ["QUALITY=90"]
        # PNG: defaults are fine (lossless).
        return []

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
        """Create a GDAL dataset for the given output driver."""
        driver = gdal.GetDriverByName(driver_name)
        if driver is None:
            raise ExportError("ERR_GDAL_DRIVER_MISSING", f"GDAL driver not found: {driver_name}")
        return driver.Create(
            output_path,
            int(width),
            int(height),
            int(bands),
            gdal.GDT_Byte,
            options=options,
        )

    def _rgba_to_rgb_on_white(self, arr_rgba: np.ndarray) -> np.ndarray:
        """Composite RGBA onto a white background; return RGB uint8 (for JPEG)."""
        if arr_rgba.ndim != 3 or arr_rgba.shape[2] != 4:
            raise ValueError("Expected RGBA array (H, W, 4)")

        rgb = arr_rgba[:, :, :3].astype(np.float32)
        a = (arr_rgba[:, :, 3:4].astype(np.float32)) / 255.0
        white = np.full_like(rgb, 255.0, dtype=np.float32)
        out = rgb * a + white * (1.0 - a)
        return np.clip(out, 0.0, 255.0).astype(np.uint8)

    def _write_prj_file(self, output_path: str, crs: QgsCoordinateReferenceSystem) -> None:
        """Write .prj (WKT) next to output raster/tile."""
        root, _ = os.path.splitext(output_path)
        prj_path = root + ".prj"
        wkt = self._crs_to_wkt(crs)  # nutzt deine bestehende Methode
        Path(prj_path).write_text(wkt, encoding="utf-8")

    def _worldfile_extension_for(self, output_path: str) -> str:
        """Return worldfile extension for the raster format."""
        ext = (Path(output_path).suffix or "").lower()
        if ext in {".tif", ".tiff"}:
            return ".tfw"
        if ext == ".png":
            return ".pgw"
        if ext in {".jpg", ".jpeg"}:
            return ".jgw"
        return ".wld"

    def _write_world_file(self, path: str, geotransform: list[float]) -> None:
        """Write a world file next to the raster (extension depends on format)."""
        root, _ = os.path.splitext(path)
        world_path = root + self._worldfile_extension_for(path)

        gt0, gt1, gt2, gt3, gt4, gt5 = geotransform
        x_center = gt0 + gt1 * 0.5 + gt2 * 0.5
        y_center = gt3 + gt4 * 0.5 + gt5 * 0.5

        with open(world_path, "w", encoding="ascii") as fh:
            fh.write(f"{gt1:.12f}\n")
            fh.write(f"{gt4:.12f}\n")
            fh.write(f"{gt2:.12f}\n")
            fh.write(f"{gt5:.12f}\n")
            fh.write(f"{x_center:.12f}\n")
            fh.write(f"{y_center:.12f}\n")

    def _write_sidecars(
        self,
        path: str,
        geotransform: list[float],
        crs: QgsCoordinateReferenceSystem,
    ) -> None:
        """Write world file and .prj or fail with a clear export error."""
        try:
            self._write_world_file(path, geotransform)
        except Exception as ex:
            raise ExportError(
                "ERR_SIDECAR_WRITE_FAILED",
                f"Failed to write world file for '{path}': {ex}",
            )

        try:
            self._write_prj_file(path, crs)
        except Exception as ex:
            raise ExportError(
                "ERR_SIDECAR_WRITE_FAILED",
                f"Failed to write .prj for '{path}': {ex}",
            )

