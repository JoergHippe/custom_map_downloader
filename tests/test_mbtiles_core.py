import sqlite3
from itertools import islice
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tests.test_exporter_validation import install_qgis_stubs

install_qgis_stubs()

from custom_map_downloader.core.mbtiles import (  # noqa: E402
    auto_detect_min_zoom,
    build_mbtiles_plan,
    count_tiles,
    create_mbtiles_database,
    insert_tile,
    staged_mbtiles_path,
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

    def test_tile_plan_is_lazy_and_repeatable(self):
        bounds = (-180.0, -85.0, 180.0, 85.0)
        plan = build_mbtiles_plan(
            bounds, zoom_min=0, zoom_max=22, tile_size=256, padding=0
        )
        # The full world through z22 represents trillions of tiles. The
        # plan must remain cheap; only the first few objects get created.
        self.assertGreater(plan.tile_count, 1_000_000_000)
        first = list(islice(plan.tiles, 3))
        self.assertEqual([(tile.zoom, tile.x, tile.y) for tile in first],
                         [(0, 0, 0), (1, 0, 0), (1, 1, 0)])
        self.assertEqual(
            [(tile.zoom, tile.x, tile.y) for tile in islice(plan.tiles, 3)],
            [(tile.zoom, tile.x, tile.y) for tile in first],
        )
        self.assertNotIsInstance(plan.tiles, (tuple, list))

    def test_tile_progress_has_stable_final_percent(self):
        plan = build_mbtiles_plan(
            (-1.0, -1.0, 1.0, 1.0),
            zoom_min=0,
            zoom_max=3,
            tile_size=256,
            padding=1,
            base_percent=15,
            span_percent=80,
        )
        tiles = list(plan.tiles)
        self.assertEqual(len(tiles), plan.tile_count)
        percents = [tile.percent for tile in tiles]
        self.assertEqual(percents[-1], 95)
        self.assertEqual(percents, sorted(percents))

    def test_staged_export_preserves_existing_file_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "existing.mbtiles"
            target.write_bytes(b"prior successful export")

            with self.assertRaisesRegex(RuntimeError, "render failed"):
                with staged_mbtiles_path(target) as staged:
                    conn = create_mbtiles_database(staged)
                    try:
                        conn.execute("INSERT INTO metadata VALUES (?, ?)", ("key", "val"))
                        conn.commit()
                    finally:
                        conn.close()
                    raise RuntimeError("render failed")

            self.assertEqual(target.read_bytes(), b"prior successful export")
            self.assertEqual(sorted(p.name for p in Path(tmp_dir).iterdir()), [target.name])

    def test_staged_export_replaces_destination_after_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "existing.mbtiles"
            target.write_bytes(b"prior successful export")

            with staged_mbtiles_path(target) as staged:
                conn = create_mbtiles_database(staged)
                try:
                    conn.execute("INSERT INTO metadata VALUES (?, ?)", ("name", "new"))
                    conn.commit()
                finally:
                    conn.close()
                self.assertEqual(target.read_bytes(), b"prior successful export")

            with sqlite3.connect(target) as conn:
                self.assertEqual(conn.execute("SELECT value FROM metadata").fetchone(), ("new",))
            self.assertEqual(sorted(p.name for p in Path(tmp_dir).iterdir()), [target.name])

    def test_create_database_rejects_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "existing.mbtiles"
            target.write_bytes(b"do not touch")
            with self.assertRaises(FileExistsError):
                create_mbtiles_database(target)
            self.assertEqual(target.read_bytes(), b"do not touch")

    def test_schema_creation_failure_closes_sqlite_connection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "new.mbtiles"
            connection = Mock()
            connection.executescript.side_effect = sqlite3.OperationalError("disk full")

            # Patch the shared sqlite3 module directly; the unit-test QGIS
            # stubs do not always attach submodules as package attributes.
            with patch.object(sqlite3, "connect", return_value=connection):
                with self.assertRaises(sqlite3.OperationalError):
                    create_mbtiles_database(target)

            connection.close.assert_called_once_with()

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
                insert_tile(conn, next(iter(plan.tiles)), b"png")
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
