# -*- coding: utf-8 -*-

"""Tile sizing and tiled-export geometry helpers."""

from __future__ import annotations

from qgis.core import QgsRectangle

from .models import ExportParams


def pick_tile_size(params: ExportParams, *, default_max_tile_px: int) -> tuple[int, int]:
    """Pick tile width/height from params with sane defaults."""
    preset = int(params.vrt_preset_size or 0)

    tile_width = int(params.vrt_max_cols or 0)
    tile_height = int(params.vrt_max_rows or 0)

    if tile_width <= 0 and preset > 0:
        tile_width = preset
    if tile_height <= 0 and preset > 0:
        tile_height = preset

    if tile_width <= 0:
        tile_width = default_max_tile_px
    if tile_height <= 0:
        tile_height = default_max_tile_px

    tile_width = max(64, min(8192, tile_width))
    tile_height = max(64, min(8192, tile_height))
    return tile_width, tile_height


def pad_extent_to_full_tiles(
    extent: QgsRectangle,
    *,
    width_px: int,
    height_px: int,
    tile_width_px: int,
    tile_height_px: int,
) -> tuple[QgsRectangle, int, int]:
    """Expand extent symmetrically so width/height align with the tile grid."""
    px_w = extent.width() / float(width_px)
    px_h = extent.height() / float(height_px)

    cols = (width_px + tile_width_px - 1) // tile_width_px
    rows = (height_px + tile_height_px - 1) // tile_height_px

    new_width = cols * tile_width_px
    new_height = rows * tile_height_px

    dx_px = new_width - width_px
    dy_px = new_height - height_px

    dx_map = dx_px * px_w
    dy_map = dy_px * px_h

    padded_extent = QgsRectangle(
        extent.xMinimum() - dx_map / 2.0,
        extent.yMinimum() - dy_map / 2.0,
        extent.xMaximum() + dx_map / 2.0,
        extent.yMaximum() + dy_map / 2.0,
    )
    return padded_extent, new_width, new_height
