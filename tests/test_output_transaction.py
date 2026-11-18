"""Filesystem safety for staged raster and VRT publications (no QGIS required)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from custom_map_downloader.core.output_transaction import staged_raster_output


class StagedRasterOutputTests(unittest.TestCase):
    def test_success_replaces_existing_primary_and_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.tif"
            dest.write_bytes(b"old")
            dest.with_suffix(".prj").write_bytes(b"old-prj")
            with staged_raster_output(dest) as staged:
                staged.write_bytes(b"new")
                staged.with_suffix(".prj").write_bytes(b"new-prj")
                self.assertEqual(dest.read_bytes(), b"old")
            self.assertEqual(dest.read_bytes(), b"new")
            self.assertEqual(dest.with_suffix(".prj").read_bytes(), b"new-prj")

    def test_export_exception_preserves_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.tif"
            dest.write_bytes(b"old")
            with self.assertRaisesRegex(RuntimeError, "cancel"):
                with staged_raster_output(dest) as staged:
                    staged.write_bytes(b"partial")
                    raise RuntimeError("cancel")
            self.assertEqual(dest.read_bytes(), b"old")
            self.assertEqual([item.name for item in Path(directory).iterdir()], ["map.tif"])

    def test_missing_output_does_not_touch_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.tif"
            dest.write_bytes(b"old")
            with self.assertRaisesRegex(RuntimeError, "primary output"):
                with staged_raster_output(dest):
                    pass
            self.assertEqual(dest.read_bytes(), b"old")

    def test_vrt_preserves_old_tiles_on_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.vrt"
            tile = Path(directory) / "map__tile_r000_c000.tif"
            dest.write_bytes(b"old-vrt")
            tile.write_bytes(b"old-tile")
            with self.assertRaises(ValueError):
                with staged_raster_output(dest) as staged:
                    staged.write_bytes(b"new-vrt")
                    (staged.parent / tile.name).write_bytes(b"new-tile")
                    raise ValueError("render")
            self.assertEqual(dest.read_bytes(), b"old-vrt")
            self.assertEqual(tile.read_bytes(), b"old-tile")

    def test_failed_vrt_publish_rolls_back_replaced_tiles_and_vrt(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.vrt"
            tile = Path(directory) / "map__tile_r000_c000.tif"
            dest.write_bytes(b"old-vrt")
            tile.write_bytes(b"old-tile")
            original_replace = os.replace

            def replace_with_failure(src, dst):
                # Fail only the new VRT publication, not rollback of its backup.
                if Path(src).name == "map.vrt" and Path(src).parent.name.startswith(".map.stage-"):
                    raise OSError("simulated publish failure")
                return original_replace(src, dst)

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=replace_with_failure,
            ):
                with self.assertRaisesRegex(OSError, "simulated publish"):
                    with staged_raster_output(dest) as staged:
                        staged.write_bytes(b"new-vrt")
                        (staged.parent / tile.name).write_bytes(b"new-tile")
            self.assertEqual(dest.read_bytes(), b"old-vrt")
            self.assertEqual(tile.read_bytes(), b"old-tile")


if __name__ == "__main__":
    unittest.main()
