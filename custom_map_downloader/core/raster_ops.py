# -*- coding: utf-8 -*-

"""Raster writing and warp helpers used by the exporter."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
from osgeo import gdal
from qgis.core import QgsCoordinateReferenceSystem, QgsRectangle
from qgis.PyQt.QtGui import QImage

from .errors import ExportError


def qimage_to_rgba_array(rendered_image: QImage, *, width: int, height: int) -> np.ndarray:
    """Convert a QImage into an RGBA numpy array."""
    rendered_image = rendered_image.convertToFormat(QImage.Format_RGBA8888)
    ptr = rendered_image.bits()
    byte_count = (
        rendered_image.sizeInBytes()
        if hasattr(rendered_image, "sizeInBytes")
        else rendered_image.byteCount()
    )
    ptr.setsize(byte_count)
    return np.frombuffer(ptr, dtype=np.uint8).reshape(height, width, 4)


def ensure_not_fully_transparent(arr_rgba: np.ndarray, *, height: int, width: int) -> None:
    """Fail if a rendered RGBA array is fully transparent."""
    step_y = max(1, height // 200)
    step_x = max(1, width // 200)
    alpha_sample = arr_rgba[::step_y, ::step_x, 3]
    if int(alpha_sample.max()) == 0:
        raise ExportError(
            "ERR_RENDER_EMPTY",
            "Rendered image is fully transparent. Likely network timeout or service WIDTH/HEIGHT limit. "
            "Try smaller size, higher timeout, or tiling.",
        )


def build_geotransform(extent: QgsRectangle, *, width: int, height: int) -> list[float]:
    """Build a GDAL geotransform from extent and raster size."""
    px_w = extent.width() / float(width)
    px_h = extent.height() / float(height)
    return [extent.xMinimum(), px_w, 0.0, extent.yMaximum(), 0.0, -px_h]


def write_full_raster(
    *,
    output_path: str,
    arr: np.ndarray,
    geotransform: list[float],
    output_crs: QgsCoordinateReferenceSystem,
    driver_name: str,
    gdal_create_options: Callable[[str], list[str]],
    gdal_create_dataset: Callable[..., Any],
    crs_to_wkt: Callable[[QgsCoordinateReferenceSystem], str],
    check_cancel: Callable[..., None],
    cancel_token: Any,
) -> None:
    """Write a full raster array to disk via GDAL."""
    height, width, bands = arr.shape
    dataset = gdal_create_dataset(
        output_path=output_path,
        driver_name=driver_name,
        width=width,
        height=height,
        bands=bands,
        options=gdal_create_options(driver_name),
    )
    if dataset is None:
        raise ExportError(
            "ERR_GDAL_CREATE_FAILED",
            f"driver.Create returned None (driver={driver_name}).",
        )

    try:
        dataset.SetGeoTransform(geotransform)
        dataset.SetProjection(crs_to_wkt(output_crs))

        for i in range(bands):
            check_cancel(cancel_token)
            band = dataset.GetRasterBand(i + 1)
            band.WriteArray(arr[:, :, i])
            band.FlushCache()
    finally:
        dataset = None


def warp_rendered_raster(
    *,
    source_path: str,
    final_output_path: str,
    render_extent: QgsRectangle,
    render_crs: QgsCoordinateReferenceSystem,
    output_crs: QgsCoordinateReferenceSystem,
    transform_extent_rect: Callable[..., QgsRectangle],
    driver_for_output: Callable[[str], str],
    crs_to_wkt: Callable[[QgsCoordinateReferenceSystem], str],
    gdal_create_options: Callable[[str], list[str]],
    write_sidecars: Callable[[str, list[float], QgsCoordinateReferenceSystem], None],
    report: Callable[..., None],
    progress_cb: Any,
    check_cancel: Callable[..., None],
    cancel_token: Any,
) -> str:
    """Reproject an intermediate rendered raster into the requested output CRS."""
    check_cancel(cancel_token)
    src_ds = gdal.Open(source_path)
    if src_ds is None:
        raise ExportError("ERR_WARP_FAILED", f"Failed to open intermediate raster: {source_path}")

    width = int(getattr(src_ds, "RasterXSize", 0) or 0)
    height = int(getattr(src_ds, "RasterYSize", 0) or 0)
    if width <= 0 or height <= 0:
        raise ExportError("ERR_WARP_FAILED", "Intermediate raster has invalid dimensions.")

    output_extent = transform_extent_rect(
        render_extent,
        src_crs=render_crs,
        dst_crs=output_crs,
    )
    warp_kwargs: dict[str, Any] = {
        "format": driver_for_output(final_output_path),
        "dstSRS": crs_to_wkt(output_crs),
        "outputBounds": [
            output_extent.xMinimum(),
            output_extent.yMinimum(),
            output_extent.xMaximum(),
            output_extent.yMaximum(),
        ],
        "width": width,
        "height": height,
        "creationOptions": gdal_create_options(driver_for_output(final_output_path)),
    }

    warped_ds = None
    try:
        warped_ds = gdal.Warp(final_output_path, src_ds, **warp_kwargs)
    except Exception as ex:
        raise ExportError("ERR_WARP_FAILED", f"GDAL warp failed: {ex}") from ex
    finally:
        src_ds = None

    if warped_ds is None:
        raise ExportError("ERR_WARP_FAILED", "GDAL warp returned no dataset.")

    try:
        geotransform = list(warped_ds.GetGeoTransform())
        warped_ds.FlushCache()
    except Exception as ex:
        raise ExportError("ERR_WARP_FAILED", f"Failed to finalize warped raster: {ex}") from ex
    finally:
        warped_ds = None

    write_sidecars(final_output_path, geotransform, output_crs)
    report(progress_cb, 100, "STEP_DONE", {"step": 6, "total": 6})
    return final_output_path
