# -*- coding: utf-8 -*-

"""Rendering and tiled retry helpers."""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Optional

import numpy as np
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMapLayer,
    QgsMapRendererParallelJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QCoreApplication, QSize
from qgis.PyQt.QtGui import QColor, QImage

from .errors import ExportError
from .models import CancelToken
from .tiling import TileSpec

ProgressCallback = Callable[[int, str, dict[str, Any]], None]
CheckCancelCallback = Callable[..., None]


def layer_extent_in_render_crs(
    layer: QgsMapLayer,
    *,
    render_crs: QgsCoordinateReferenceSystem,
) -> Optional[QgsRectangle]:
    """Return the layer extent transformed into render CRS if possible."""
    try:
        layer_extent = layer.extent()
        if layer.crs().isValid() and render_crs.isValid() and layer.crs() != render_crs:
            transform = QgsCoordinateTransform(layer.crs(), render_crs, QgsProject.instance())
            return transform.transformBoundingBox(layer_extent)
        return layer_extent
    except Exception:
        return None


def wait_with_events(
    seconds: float,
    *,
    check_cancel: CheckCancelCallback,
    cancel_token: Optional[CancelToken],
    render_job: Optional[QgsMapRendererParallelJob] = None,
) -> None:
    """Wait while keeping the UI responsive and honoring cancellation."""
    end_t = time.monotonic() + max(0.0, float(seconds))
    while time.monotonic() < end_t:
        check_cancel(cancel_token, render_job=render_job)
        QCoreApplication.processEvents()
        time.sleep(0.05)


def render_tile_rgba(
    *,
    layer: QgsMapLayer,
    tile_extent: QgsRectangle,
    render_crs: QgsCoordinateReferenceSystem,
    width_px: int,
    height_px: int,
    output_dpi: Optional[float],
    cancel_token: Optional[CancelToken],
    check_cancel: CheckCancelCallback,
) -> np.ndarray:
    """Render one tile into a detached RGBA array (height_px, width_px, 4)."""
    map_settings = QgsMapSettings()
    map_settings.setBackgroundColor(QColor(255, 255, 255))
    map_settings.setLayers([layer])
    map_settings.setExtent(tile_extent)
    map_settings.setOutputSize(QSize(width_px, height_px))
    map_settings.setDestinationCrs(render_crs)
    if output_dpi and output_dpi > 0:
        map_settings.setOutputDpi(float(output_dpi))

    job = QgsMapRendererParallelJob(map_settings)
    job.start()

    while job.isActive():
        check_cancel(cancel_token, render_job=job)
        QCoreApplication.processEvents()

    job.waitForFinished()

    img = job.renderedImage().convertToFormat(QImage.Format_RGBA8888)
    ptr = img.bits()
    byte_count = img.sizeInBytes() if hasattr(img, "sizeInBytes") else img.byteCount()
    ptr.setsize(byte_count)

    buf = np.frombuffer(ptr, dtype=np.uint8).copy()
    return buf.reshape(height_px, width_px, 4)


def render_tile_with_retry(
    *,
    tile: TileSpec,
    layer: QgsMapLayer,
    render_crs: QgsCoordinateReferenceSystem,
    output_dpi: Optional[float],
    cancel_token: Optional[CancelToken],
    layer_extent_render: Optional[QgsRectangle],
    progress_cb: Optional[ProgressCallback],
    report: Callable[[Optional[ProgressCallback], int, str, Optional[dict[str, Any]]], None],
    wait_fn: Callable[..., None],
    render_fn: Callable[..., np.ndarray],
    check_cancel: CheckCancelCallback,
    max_retries: int = 3,
    base_backoff_s: float = 0.7,
    max_backoff_s: float = 8.0,
) -> tuple[np.ndarray, bool]:
    """Render a tile with retry/backoff logic and blank-tile detection."""
    tile_overlaps_layer = True
    if layer_extent_render is not None:
        try:
            tile_overlaps_layer = tile.extent.intersects(layer_extent_render)
        except Exception:
            tile_overlaps_layer = True

    arr: Optional[np.ndarray] = None
    was_blank = False

    for attempt in range(max_retries + 1):
        check_cancel(cancel_token)

        try:
            arr = render_fn(
                layer=layer,
                tile_extent=tile.extent,
                render_crs=render_crs,
                width_px=tile.width_px,
                height_px=tile.height_px,
                output_dpi=output_dpi,
                cancel_token=cancel_token,
            )
        except Exception as ex:
            if attempt < max_retries:
                backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
                backoff *= 0.8 + 0.4 * random.random()
                report(
                    progress_cb,
                    tile.percent,
                    "WARN_TILE_RETRY",
                    {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
                )
                wait_fn(backoff, cancel_token=cancel_token)
                continue
            raise ExportError("ERR_RENDER_TILE_FAILED", str(ex)) from ex

        sy = max(1, tile.height_px // 64)
        sx = max(1, tile.width_px // 64)
        alpha_max = int(arr[::sy, ::sx, 3].max())
        was_blank = alpha_max == 0

        if not was_blank:
            break

        if attempt < max_retries and tile_overlaps_layer:
            backoff = min(max_backoff_s, base_backoff_s * (2**attempt))
            backoff *= 0.8 + 0.4 * random.random()
            report(
                progress_cb,
                tile.percent,
                "WARN_TILE_RETRY",
                {"attempt": attempt + 1, "max": max_retries, "seconds": backoff},
            )
            wait_fn(backoff, cancel_token=cancel_token)
            continue

        break

    if arr is None:
        raise ExportError("ERR_RENDER_TILE_FAILED", "Tile render returned no buffer.")

    return arr, was_blank
