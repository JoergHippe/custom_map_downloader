"""Filesystem safety for staged raster and VRT publications (no QGIS required)."""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from custom_map_downloader.core.errors import CancelledError, ExportError
from custom_map_downloader.core.output_transaction import (
    should_use_local_work,
    staged_raster_output,
)


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
            with self.assertRaises(ExportError) as ctx:
                with staged_raster_output(dest):
                    pass
            self.assertEqual(ctx.exception.code, "ERR_EXPORT_STAGE_INCOMPLETE")
            self.assertIn("primary output", ctx.exception.details)
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
                with self.assertRaises(ExportError) as ctx:
                    with staged_raster_output(dest) as staged:
                        staged.write_bytes(b"new-vrt")
                        (staged.parent / tile.name).write_bytes(b"new-tile")
            self.assertEqual(ctx.exception.code, "ERR_EXPORT_PUBLISH_ROLLED_BACK")
            self.assertIn("restored", ctx.exception.details)
            self.assertEqual(dest.read_bytes(), b"old-vrt")
            self.assertEqual(tile.read_bytes(), b"old-tile")

    def test_failed_rollback_preserves_backups_and_reports_recovery_path(self):
        """Do not claim restoration when the original tile cannot be restored."""
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.vrt"
            tile = Path(directory) / "map__tile_r000_c000.tif"
            dest.write_bytes(b"original-vrt")
            tile.write_bytes(b"original-tile")
            original_replace = os.replace

            def replace_with_failure(src, dst):
                src = Path(src)
                dst = Path(dst)
                if src.name == "map.vrt" and src.parent.name.startswith(".map.stage-"):
                    raise OSError("publish interrupted")
                if src.name == tile.name and src.parent.name == ".backups":
                    raise OSError("tile restore blocked")
                return original_replace(src, dst)

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=replace_with_failure,
            ):
                with self.assertRaises(ExportError) as ctx:
                    with staged_raster_output(dest) as staged:
                        staged.write_bytes(b"new-vrt")
                        (staged.parent / tile.name).write_bytes(b"new-tile")

            self.assertEqual(ctx.exception.code, "ERR_EXPORT_PUBLISH_RECOVERY_REQUIRED")
            self.assertEqual(dest.read_bytes(), b"original-vrt")
            recovery_dirs = list(Path(directory).glob(".map.recovery-*"))
            self.assertEqual(len(recovery_dirs), 1)
            self.assertEqual((recovery_dirs[0] / tile.name).read_bytes(), b"original-tile")
            self.assertIn(str(recovery_dirs[0]), ctx.exception.details)
            self.assertFalse(tile.exists())

    def test_failed_recovery_move_keeps_staging_backups(self):
        """Backup files must survive even when recovery-folder rename fails."""
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "map.vrt"
            tile = Path(directory) / "map__tile_r000_c000.tif"
            dest.write_bytes(b"old-vrt")
            tile.write_bytes(b"old-tile")
            original_replace = os.replace
            original_rename = Path.rename

            def fail_replace(src, dst):
                src = Path(src)
                if src.name == "map.vrt" and src.parent.name.startswith(".map.stage-"):
                    raise OSError("publish interrupted")
                if src.name == tile.name and src.parent.name == ".backups":
                    raise OSError("restore refused")
                return original_replace(src, dst)

            def fail_recovery_move(path, target):
                if path.name == ".backups":
                    raise OSError("recovery relocation refused")
                return original_rename(path, target)

            with (
                patch(
                    "custom_map_downloader.core.output_transaction.os.replace",
                    side_effect=fail_replace,
                ),
                patch(
                    "custom_map_downloader.core.output_transaction.Path.rename",
                    new=fail_recovery_move,
                ),
            ):
                with self.assertRaises(ExportError) as ctx:
                    with staged_raster_output(dest) as staged:
                        staged.write_bytes(b"new-vrt")
                        (staged.parent / tile.name).write_bytes(b"new-tile")

            self.assertEqual(ctx.exception.code, "ERR_EXPORT_PUBLISH_RECOVERY_REQUIRED")
            staging_dirs = list(Path(directory).glob(".map.stage-*"))
            self.assertEqual(len(staging_dirs), 1)
            self.assertEqual(
                (staging_dirs[0] / ".backups" / tile.name).read_bytes(),
                b"old-tile",
            )
            self.assertIn(str(staging_dirs[0]), ctx.exception.details)
            self.assertEqual(dest.read_bytes(), b"old-vrt")

    def test_qgis_slow_device_selection_and_fast_local_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "map.tif"
            self.assertTrue(should_use_local_work(target, lambda _path: False))
            self.assertTrue(should_use_local_work(target, lambda path: path == str(target.parent)))
            self.assertFalse(
                should_use_local_work(target, lambda path: path == tempfile.gettempdir())
            )

    def test_user_temp_workspace_publishes_raster_and_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.tif"
            target.write_bytes(b"old")
            with staged_raster_output(target, prefer_local=True) as work:
                self.assertTrue(work.parent.name.startswith("cmd-work-"))
                self.assertNotEqual(work.parent, target.parent)
                work.write_bytes(b"new")
                work.with_suffix(".prj").write_bytes(b"projection")
                self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(target.read_bytes(), b"new")
            self.assertEqual(target.with_suffix(".prj").read_bytes(), b"projection")

    def test_locally_rendered_vrt_is_published_last(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.vrt"
            published = []
            original_replace = os.replace

            def track_publication(src, dst):
                if Path(dst).parent == target.parent and Path(dst).is_file() is False:
                    # Record replacements of new outputs into the final folder.
                    if Path(src).parent.name.startswith(".map.stage-"):
                        published.append(Path(dst).name)
                return original_replace(src, dst)

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=track_publication,
            ):
                with staged_raster_output(target, prefer_local=True) as staged:
                    staged.write_bytes(b"vrt")
                    (staged.parent / "map__tile_r000_c000.tif").write_bytes(b"tile")
            self.assertEqual(
                published,
                ["map__tile_r000_c000.tif", "map.vrt"],
            )

    def test_cross_device_fallback_copies_complete_vrt_file_set(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.vrt"
            original_replace = os.replace

            def force_cross_device_copy(src, dst):
                if Path(src).parent.name.startswith("cmd-work-"):
                    raise OSError("simulated cross-device rename")
                return original_replace(src, dst)

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=force_cross_device_copy,
            ):
                with staged_raster_output(target, prefer_local=True) as staged:
                    staged.write_bytes(b"vrt-xml")
                    (staged.parent / "map__tile_r000_c000.tif").write_bytes(b"tile")
                    (staged.parent / "map__tile_r000_c000.prj").write_bytes(b"crs")
            self.assertEqual(target.read_bytes(), b"vrt-xml")
            self.assertEqual((target.parent / "map__tile_r000_c000.tif").read_bytes(), b"tile")
            self.assertEqual((target.parent / "map__tile_r000_c000.prj").read_bytes(), b"crs")

    def test_cross_device_copy_cancellation_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.tif"
            target.write_bytes(b"old")
            original_replace = os.replace
            counts = {"checks": 0}

            def force_copy_for_workdir(src, dst):
                if Path(src).parent.name.startswith("cmd-work-"):
                    raise OSError("simulated cross-device rename")
                return original_replace(src, dst)

            def check_cancel():
                counts["checks"] += 1
                if counts["checks"] >= 3:
                    raise CancelledError("ERR_CANCELLED", "cancel during transfer")

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=force_copy_for_workdir,
            ):
                with self.assertRaises(CancelledError):
                    with staged_raster_output(
                        target, prefer_local=True, check_cancel=check_cancel
                    ) as work:
                        work.write_bytes(b"x" * (16 * 1024 * 1024))
            self.assertEqual(target.read_bytes(), b"old")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["map.tif"])

    def test_local_space_shortage_falls_back_before_rendering(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.tif"
            with patch(
                "custom_map_downloader.core.output_transaction.shutil.disk_usage",
                return_value=SimpleNamespace(free=0),
            ):
                with staged_raster_output(target, prefer_local=True) as staged:
                    self.assertTrue(staged.parent.name.startswith(".map.stage-"))
                    staged.write_bytes(b"fallback")
            self.assertEqual(target.read_bytes(), b"fallback")

    def test_locked_destination_keeps_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "map.tif"
            target.write_bytes(b"old")
            original_replace = os.replace

            def locked_target(src, dst):
                if Path(dst) == target and Path(src).parent.name.startswith(".map.stage-"):
                    raise PermissionError("simulated Windows file lock")
                return original_replace(src, dst)

            with patch(
                "custom_map_downloader.core.output_transaction.os.replace",
                side_effect=locked_target,
            ):
                with self.assertRaises(ExportError) as ctx:
                    with staged_raster_output(target, prefer_local=True) as work:
                        work.write_bytes(b"new")
            self.assertEqual(ctx.exception.code, "ERR_EXPORT_PUBLISH_ROLLED_BACK")
            self.assertEqual(target.read_bytes(), b"old")


if __name__ == "__main__":
    unittest.main()
