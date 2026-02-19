# CustomMapDownloader/core/validation.py
# -*- coding: utf-8 -*-

"""Shared validation helpers for UI and exporter."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from qgis.core import Qgis, QgsUnitTypes, QgsCoordinateReferenceSystem

from .constants import (
    GSD_MIN,
    GSD_MAX,
    LARGE_RASTER_STRONG_MAX_DIM_PX,
    LARGE_RASTER_STRONG_TOTAL_PX,
)
from .errors import ValidationError


def validate_output_path(output_path: str) -> None:
    """Ensure output_path exists, is writable, and has a supported extension."""
    if not output_path:
        raise ValidationError("ERR_VALIDATION_OUTPUT_MISSING", "No output_path provided.")

    path_obj = Path(output_path)
    suffix = (path_obj.suffix or "").lower()
    allowed = {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".vrt"}
    if suffix not in allowed:
        raise ValidationError(
            "ERR_VALIDATION_OUTPUT_EXT",
            f"Unsupported output extension: {suffix or '<none>'}",
        )

    parent = path_obj.parent if str(path_obj.parent) else Path(".")
    if not parent.exists() or not parent.is_dir():
        raise ValidationError(
            "ERR_VALIDATION_OUTPUT_DIR",
            f"Output directory does not exist: {parent}",
        )
    if not os.access(parent, os.W_OK):
        raise ValidationError(
            "ERR_VALIDATION_OUTPUT_DIR",
            f"Output directory not writable: {parent}",
        )
    if path_obj.exists():
        if path_obj.is_dir():
            raise ValidationError(
                "ERR_VALIDATION_OUTPUT_DIR",
                f"Output path points to a directory: {path_obj}",
            )
        if not os.access(path_obj, os.W_OK):
            raise ValidationError(
                "ERR_VALIDATION_OUTPUT_DIR",
                f"Output file not writable: {path_obj}",
            )


def validate_gsd(gsd: float) -> None:
    """Validate GSD against configured min/max."""
    if gsd <= 0 or gsd < GSD_MIN or gsd > GSD_MAX:
        raise ValidationError(
            "ERR_VALIDATION_GSD_INVALID",
            f"Invalid gsd_m_per_px: {gsd} (allowed {GSD_MIN}..{GSD_MAX})",
        )


def validate_pixel_limits(width_px: int, height_px: int) -> None:
    """Validate strong raster size limits."""
    if (
        width_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
        or height_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
        or (width_px * height_px) >= LARGE_RASTER_STRONG_TOTAL_PX
    ):
        raise ValidationError(
            "ERR_VALIDATION_SIZE_TOO_LARGE",
            (
                f"Raster size too large: {width_px}x{height_px} px "
                f"(total {width_px * height_px:,} px)"
            ),
        )


def crs_uses_meters(crs: QgsCoordinateReferenceSystem) -> bool:
    """Return True if CRS map units are meters."""
    try:
        return crs.mapUnits() == Qgis.DistanceUnit.Meters
    except Exception:
        try:
            return QgsUnitTypes.toString(crs.mapUnits()).lower().startswith("meter")
        except Exception:
            return False


def pixel_limit_status(width_px: int, height_px: int) -> Tuple[str, str]:
    """Return ("ok"/"warn"/"strong", message) for pixel sizes."""
    total_px = int(width_px) * int(height_px)

    if (
        width_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
        or height_px >= LARGE_RASTER_STRONG_MAX_DIM_PX
        or total_px >= LARGE_RASTER_STRONG_TOTAL_PX
    ):
        return (
            "strong",
            (
                f"Raster size exceeds hard limit ({width_px}×{height_px} px, total {total_px:,} px)."
            ),
        )

    if (
        width_px >= LARGE_RASTER_STRONG_MAX_DIM_PX // 2
        or height_px >= LARGE_RASTER_STRONG_MAX_DIM_PX // 2
        or total_px >= LARGE_RASTER_STRONG_TOTAL_PX // 2
    ):
        return (
            "warn",
            (
                f"Very large raster ({width_px}×{height_px} px, total {total_px:,} px) – may be slow or fail."
            ),
        )

    return "ok", ""
