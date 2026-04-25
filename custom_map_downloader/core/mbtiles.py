# -*- coding: utf-8 -*-

"""MBTiles tile math and SQLite helpers."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from qgis.core import QgsRectangle

WEB_MERCATOR_AUTHID = "EPSG:3857"
WGS84_AUTHID = "EPSG:4326"
WEB_MERCATOR_HALF_WORLD = 20037508.342789244
MIN_WEB_MERCATOR_LAT = -85.05112878
MAX_WEB_MERCATOR_LAT = 85.05112878
MAX_ZOOM = 22
DEFAULT_AVG_TILE_BYTES = 50 * 1024


@dataclass(frozen=True)
class MbtilesTile:
    """Single XYZ tile address plus render extent."""

    zoom: int
    x: int
    y: int
    tms_y: int
    extent_3857: QgsRectangle
    percent: int


@dataclass(frozen=True)
class MbtilesPlan:
    """Complete MBTiles export plan."""

    bounds_4326: tuple[float, float, float, float]
    zoom_min: int
    zoom_max: int
    tile_size: int
    padding: int
    tiles: tuple[MbtilesTile, ...]

    @property
    def tile_count(self) -> int:
        return len(self.tiles)

    @property
    def estimated_bytes(self) -> int:
        return estimate_mbtiles_size(self.tile_count)


def clamp_lat(lat: float) -> float:
    return max(MIN_WEB_MERCATOR_LAT, min(MAX_WEB_MERCATOR_LAT, float(lat)))


def clamp_lon(lon: float) -> float:
    return max(-180.0, min(180.0, float(lon)))


def lon_to_tile_x(lon: float, zoom: int) -> int:
    z = int(zoom)
    n = 1 << z
    x = int(math.floor(((clamp_lon(lon) + 180.0) / 360.0) * n))
    return max(0, min(n - 1, x))


def lat_to_tile_y(lat: float, zoom: int) -> int:
    z = int(zoom)
    n = 1 << z
    lat_rad = math.radians(clamp_lat(lat))
    y = int(math.floor((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n))
    return max(0, min(n - 1, y))


def tile_x_to_lon(x: int, zoom: int) -> float:
    n = 1 << int(zoom)
    return (float(x) / n) * 360.0 - 180.0


def tile_y_to_lat(y: int, zoom: int) -> float:
    n = 1 << int(zoom)
    lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * float(y) / n)))
    return math.degrees(lat_rad)


def tile_bounds_4326(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    west = tile_x_to_lon(x, zoom)
    east = tile_x_to_lon(x + 1, zoom)
    north = tile_y_to_lat(y, zoom)
    south = tile_y_to_lat(y + 1, zoom)
    return west, south, east, north


def tile_bounds_3857(x: int, y: int, zoom: int) -> QgsRectangle:
    n = 1 << int(zoom)
    tile_span = (WEB_MERCATOR_HALF_WORLD * 2.0) / float(n)
    xmin = -WEB_MERCATOR_HALF_WORLD + (x * tile_span)
    xmax = xmin + tile_span
    ymax = WEB_MERCATOR_HALF_WORLD - (y * tile_span)
    ymin = ymax - tile_span
    return QgsRectangle(xmin, ymin, xmax, ymax)


def normalize_bounds(
    west: float,
    south: float,
    east: float,
    north: float,
) -> tuple[float, float, float, float]:
    w = clamp_lon(west)
    e = clamp_lon(east)
    s = clamp_lat(south)
    n = clamp_lat(north)
    if e <= w or n <= s:
        raise ValueError("Invalid MBTiles bounds.")
    return w, s, e, n


def tile_range_for_bounds(
    bounds_4326: tuple[float, float, float, float],
    zoom: int,
    *,
    padding: int = 0,
) -> tuple[int, int, int, int]:
    west, south, east, north = normalize_bounds(*bounds_4326)
    z = int(zoom)
    n = 1 << z
    pad = max(0, int(padding))

    x_min = lon_to_tile_x(west, z)
    x_max = lon_to_tile_x(math.nextafter(east, west), z)
    y_min = lat_to_tile_y(north, z)
    y_max = lat_to_tile_y(math.nextafter(south, north), z)

    return (
        max(0, x_min - pad),
        min(n - 1, x_max + pad),
        max(0, y_min - pad),
        min(n - 1, y_max + pad),
    )


def count_tiles(
    bounds_4326: tuple[float, float, float, float],
    zoom_min: int,
    zoom_max: int,
    *,
    padding: int = 0,
) -> int:
    total = 0
    for z in range(int(zoom_min), int(zoom_max) + 1):
        x_min, x_max, y_min, y_max = tile_range_for_bounds(bounds_4326, z, padding=padding)
        total += (x_max - x_min + 1) * (y_max - y_min + 1)
    return total


def estimate_mbtiles_size(tile_count: int, *, avg_tile_bytes: int = DEFAULT_AVG_TILE_BYTES) -> int:
    return max(0, int(tile_count)) * max(0, int(avg_tile_bytes))


def auto_detect_min_zoom(
    bounds_4326: tuple[float, float, float, float],
    *,
    zoom_min: int = 0,
    zoom_max: int = MAX_ZOOM,
) -> int:
    for z in range(int(zoom_min), int(zoom_max) + 1):
        x_min, x_max, y_min, y_max = tile_range_for_bounds(bounds_4326, z)
        if (x_max - x_min + 1) * (y_max - y_min + 1) > 1:
            return z
    return int(zoom_max)


def build_mbtiles_plan(
    bounds_4326: tuple[float, float, float, float],
    *,
    zoom_min: int,
    zoom_max: int,
    tile_size: int,
    padding: int,
    base_percent: int = 15,
    span_percent: int = 80,
) -> MbtilesPlan:
    bounds = normalize_bounds(*bounds_4326)
    z_min = max(0, min(MAX_ZOOM, int(zoom_min)))
    z_max = max(0, min(MAX_ZOOM, int(zoom_max)))
    if z_max < z_min:
        raise ValueError("Invalid MBTiles zoom range.")

    size = int(tile_size)
    if size < 64 or size > 1024:
        raise ValueError("Invalid MBTiles tile size.")

    pad = max(0, min(5, int(padding)))
    total = count_tiles(bounds, z_min, z_max, padding=pad)
    done = 0
    tiles: list[MbtilesTile] = []

    for z in range(z_min, z_max + 1):
        x_min, x_max, y_min, y_max = tile_range_for_bounds(bounds, z, padding=pad)
        for y in range(y_min, y_max + 1):
            for x in range(x_min, x_max + 1):
                done += 1
                percent = base_percent + int((done / float(total)) * span_percent)
                tms_y = (1 << z) - 1 - y
                tiles.append(
                    MbtilesTile(
                        zoom=z,
                        x=x,
                        y=y,
                        tms_y=tms_y,
                        extent_3857=tile_bounds_3857(x, y, z),
                        percent=percent,
                    )
                )

    return MbtilesPlan(
        bounds_4326=bounds,
        zoom_min=z_min,
        zoom_max=z_max,
        tile_size=size,
        padding=pad,
        tiles=tuple(tiles),
    )


def create_mbtiles_database(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE metadata (name TEXT, value TEXT);
        CREATE TABLE tiles (
            zoom_level INTEGER NOT NULL,
            tile_column INTEGER NOT NULL,
            tile_row INTEGER NOT NULL,
            tile_data BLOB NOT NULL,
            PRIMARY KEY (zoom_level, tile_column, tile_row)
        );
        CREATE UNIQUE INDEX tile_index
            ON tiles (zoom_level, tile_column, tile_row);
        """
    )
    return conn


def write_metadata(
    conn: sqlite3.Connection,
    *,
    name: str,
    description: str,
    bounds_4326: tuple[float, float, float, float],
    zoom_min: int,
    zoom_max: int,
    tile_format: str = "png",
) -> None:
    west, south, east, north = normalize_bounds(*bounds_4326)
    rows = [
        ("name", name),
        ("type", "overlay"),
        ("version", "1"),
        ("description", description),
        ("format", tile_format),
        ("bounds", f"{west:.8f},{south:.8f},{east:.8f},{north:.8f}"),
        ("minzoom", str(int(zoom_min))),
        ("maxzoom", str(int(zoom_max))),
    ]
    conn.executemany("INSERT INTO metadata (name, value) VALUES (?, ?)", rows)


def insert_tile(conn: sqlite3.Connection, tile: MbtilesTile, tile_data: bytes) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO tiles
            (zoom_level, tile_column, tile_row, tile_data)
        VALUES (?, ?, ?, ?)
        """,
        (int(tile.zoom), int(tile.x), int(tile.tms_y), sqlite3.Binary(tile_data)),
    )
