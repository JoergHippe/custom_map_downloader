# -*- coding: utf-8 -*-

"""GDAL- and raster-format-related helper functions."""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
from osgeo import gdal, osr
from qgis.core import QgsCoordinateReferenceSystem

from .constants import GTIFF_CREATE_OPTIONS, JPEG_CREATE_OPTIONS
from .errors import ExportError


def driver_for_output(output_path: str) -> str:
    """Return GDAL driver name for the given output path suffix."""
    ext = (Path(output_path).suffix or "").lower()
    if ext in {".tif", ".tiff"}:
        return "GTiff"
    if ext == ".png":
        return "PNG"
    if ext in {".jpg", ".jpeg"}:
        return "JPEG"
    return "GTiff"


def tile_extension_for(output_path: str) -> str:
    """Normalize raster extension used for tiles."""
    ext = (Path(output_path).suffix or "").lower()
    if ext == ".tiff":
        return ".tif"
    if ext == ".jpeg":
        return ".jpg"
    if ext in {".tif", ".png", ".jpg"}:
        return ext
    if ext == ".vrt":
        return ".tif"
    return ".tif"


def gdal_create_options(driver_name: str) -> list[str]:
    """Return GDAL Create() options per driver."""
    if driver_name == "GTiff":
        return list(GTIFF_CREATE_OPTIONS)
    if driver_name == "JPEG":
        return list(JPEG_CREATE_OPTIONS)
    return []


def create_dataset(
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


def crs_to_wkt(crs: QgsCoordinateReferenceSystem) -> str:
    """Convert a QGIS CRS into WKT for GDAL/OSR."""
    if not crs.isValid():
        raise ExportError("ERR_CRS_INVALID", "CRS is not valid.")

    authid = crs.authid() or ""
    match = re.match(r"^EPSG:(\d+)$", authid)
    srs = osr.SpatialReference()

    if match:
        srs.ImportFromEPSG(int(match.group(1)))
        return srs.ExportToWkt()

    wkt = crs.toWkt()
    err = srs.ImportFromWkt(wkt)
    if err != 0:
        raise ExportError(
            "ERR_CRS_TO_WKT_FAILED",
            f"OSR ImportFromWkt failed (code={err}).",
        )
    return srs.ExportToWkt()


def rgba_to_rgb_on_white(arr_rgba: np.ndarray) -> np.ndarray:
    """Composite RGBA onto a white background; return RGB uint8."""
    if arr_rgba.ndim != 3 or arr_rgba.shape[2] != 4:
        raise ValueError("Expected RGBA array (H, W, 4)")

    rgb = arr_rgba[:, :, :3].astype(np.float32)
    alpha = (arr_rgba[:, :, 3:4].astype(np.float32)) / 255.0
    white = np.full_like(rgb, 255.0, dtype=np.float32)
    out = rgb * alpha + white * (1.0 - alpha)
    return np.clip(out, 0.0, 255.0).astype(np.uint8)


def write_prj_file(output_path: str, crs: QgsCoordinateReferenceSystem) -> None:
    """Write .prj (WKT) next to the raster."""
    root, _ = os.path.splitext(output_path)
    prj_path = root + ".prj"
    Path(prj_path).write_text(crs_to_wkt(crs), encoding="utf-8")


def worldfile_extension_for(output_path: str) -> str:
    """Return worldfile extension for the raster format."""
    ext = (Path(output_path).suffix or "").lower()
    if ext in {".tif", ".tiff"}:
        return ".tfw"
    if ext == ".png":
        return ".pgw"
    if ext in {".jpg", ".jpeg"}:
        return ".jgw"
    return ".wld"


def write_world_file(path: str, geotransform: list[float]) -> None:
    """Write a world file next to the raster."""
    root, _ = os.path.splitext(path)
    world_path = root + worldfile_extension_for(path)

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


def write_sidecars(
    path: str,
    geotransform: list[float],
    crs: QgsCoordinateReferenceSystem,
) -> None:
    """Write world file and .prj or fail with a clear export error."""
    try:
        write_world_file(path, geotransform)
    except Exception as ex:
        raise ExportError(
            "ERR_SIDECAR_WRITE_FAILED",
            f"Failed to write world file for '{path}': {ex}",
        ) from ex

    try:
        write_prj_file(path, crs)
    except Exception as ex:
        raise ExportError(
            "ERR_SIDECAR_WRITE_FAILED",
            f"Failed to write .prj for '{path}': {ex}",
        ) from ex
