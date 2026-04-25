import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.test_exporter_validation import install_qgis_stubs

install_qgis_stubs()

from custom_map_downloader.core.mbtiles import (  # noqa: E402
    auto_detect_min_zoom,
    build_mbtiles_plan,
    count_tiles,
    create_mbtiles_database,
    insert_tile,
    tile_bounds_4326,
    tile_range_for_bounds,
    write_metadata,
)


class MbtilesCoreTests(unittest.TestCase):
    def test_tile_bounds_for_world_zoom_zero(self):
        west, south, east, north = tile_bounds_4326(0, 0, 0)

        self.assertAlmostEqual(west, -180.0)
        self.assertAlmostEqual(east, 180.0)
        self.assertAlmostEqual(south, -85.05112878, places=6)
        self.assertAlmostEqual(north, 85.05112878, places=6)

    def test_tile_range_and_padding_are_clamped(self):
        bounds = (-1.0, -1.0, 1.0, 1.0)

        exact = tile_range_for_bounds(bounds, 2, padding=0)
        padded = tile_range_for_bounds(bounds, 2, padding=5)

        self.assertEqual(exact, (1, 2, 1, 2))
        self.assertEqual(padded, (0, 3, 0, 3))

    def test_count_tiles_across_zoom_range(self):
        bounds = (-1.0, -1.0, 1.0, 1.0)

        self.assertEqual(count_tiles(bounds, 0, 0), 1)
        self.assertEqual(count_tiles(bounds, 0, 1), 5)

    def test_auto_detect_min_zoom_uses_exact_bounds(self):
        bounds = (-1.0, -1.0, 1.0, 1.0)

        self.assertEqual(auto_detect_min_zoom(bounds, zoom_min=0, zoom_max=5), 1)

    def test_build_plan_uses_tms_y_flip(self):
        plan = build_mbtiles_plan(
            (-1.0, -1.0, 1.0, 1.0),
            zoom_min=2,
            zoom_max=2,
            tile_size=256,
            padding=0,
        )

        self.assertEqual(plan.tile_count, 4)
        rows = {(tile.x, tile.y, tile.tms_y) for tile in plan.tiles}
        self.assertIn((1, 1, 2), rows)
        self.assertIn((2, 2, 1), rows)

    def test_database_schema_metadata_and_tile_insert(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "out.mbtiles"
            plan = build_mbtiles_plan(
                (-1.0, -1.0, 1.0, 1.0),
                zoom_min=0,
                zoom_max=0,
                tile_size=256,
                padding=0,
            )
            conn = create_mbtiles_database(path)
            try:
                write_metadata(
                    conn,
                    name="test",
                    description="unit test",
                    bounds_4326=plan.bounds_4326,
                    zoom_min=plan.zoom_min,
                    zoom_max=plan.zoom_max,
                )
                insert_tile(conn, plan.tiles[0], b"png")
                conn.commit()
            finally:
                conn.close()

            conn = sqlite3.connect(path)
            try:
                metadata = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
                tile_row = conn.execute(
                    "SELECT zoom_level, tile_column, tile_row, tile_data FROM tiles"
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(metadata["name"], "test")
            self.assertEqual(metadata["format"], "png")
            self.assertEqual(tile_row, (0, 0, 0, b"png"))


if __name__ == "__main__":
    unittest.main()
