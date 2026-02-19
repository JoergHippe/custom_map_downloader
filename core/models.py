# CustomMapDownloader/core/models.py
# -*- coding: utf-8 -*-

"""Data models used across UI and exporter.

This module is intentionally small and UI-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qgis.core import QgsCoordinateReferenceSystem, QgsMapLayer


@dataclass(frozen=True)
class CenterSpec:
    """Center coordinate in a given CRS.

    Args:
        northing: Y in ``crs`` (typically meters in projected CRS).
        easting: X in ``crs`` (typically meters in projected CRS).
        crs: CRS of the coordinate pair.
    """

    northing: float
    easting: float
    crs: QgsCoordinateReferenceSystem


@dataclass(frozen=True)
class ExtentSpec:
    """Extent coordinates in a given CRS.

    Args:
        west: Minimum X in ``crs``.
        south: Minimum Y in ``crs``.
        east: Maximum X in ``crs``.
        north: Maximum Y in ``crs``.
        crs: CRS of the extent coordinates.
    """

    west: float
    south: float
    east: float
    north: float
    crs: QgsCoordinateReferenceSystem


@dataclass(frozen=True)
class ExportParams:
    """All parameters required to render and export a (Geo)TIFF.

    Args:
        layer: QGIS layer to render.
        width_px: Output raster width in pixels.
        height_px: Output raster height in pixels.
        gsd_m_per_px: Ground sample distance in meters per pixel (used in legacy
            center mode).
        center: Center coordinate (used when ``extent`` is not provided).
        extent: Explicit extent (preferred mode). If provided, exporter uses this
            instead of ``center``/``gsd_m_per_px``.
        output_path: Output file path.
        load_as_layer: If ``True`` load result into the QGIS project after export.
        render_crs: CRS used for rendering (must use meters if GSD is used).
        output_crs: CRS written to output GeoTIFF. Defaults to ``render_crs``.
        create_vrt: If ``True``, VRT / tiling-related logic may be enabled
            (currently used as a hint, reserved for future VRT writer support).
        vrt_max_cols: Optional maximum tile width in pixels; used to derive tile
            size for tiled rendering.
        vrt_max_rows: Optional maximum tile height in pixels; used to derive tile
            size for tiled rendering.
        vrt_preset_size: Optional preset tile size from the UI. Currently
            informational; tile size is derived from ``vrt_max_cols`` and
            ``vrt_max_rows``.
    """

    layer: QgsMapLayer
    width_px: int
    height_px: int
    gsd_m_per_px: float
    center: CenterSpec
    extent: Optional[ExtentSpec]
    output_path: str
    load_as_layer: bool
    render_crs: Optional[QgsCoordinateReferenceSystem] = None
    output_crs: Optional[QgsCoordinateReferenceSystem] = None
    create_vrt: bool = False
    vrt_max_cols: int = 0
    vrt_max_rows: int = 0
    vrt_preset_size: int = 0


@dataclass
class CancelToken:
    """Simple cancel flag shared between UI and exporter."""

    cancelled: bool = False

    def cancel(self) -> None:
        """Mark export as cancelled."""
        self.cancelled = True
