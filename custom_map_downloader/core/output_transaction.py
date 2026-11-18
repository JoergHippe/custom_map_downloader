"""Stage raster output beside the destination; publish only on success.

One file can be replaced atomically on a single filesystem. A VRT with its
tiles and sidecars is a multi-file set: rollback is supported, but publication
cannot be atomic as a whole using ordinary filesystem operations.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import ExportError


@contextmanager
def staged_raster_output(output_path: str | Path) -> Iterator[Path]:
    """Stage outputs in the target directory and publish on clean exit.

    Before replacing a destination, its original file is backed up using a
    same-filesystem rename. If publishing fails, newly installed files are
    removed and the previous files are restored. Unrelated and obsolete VRT
    tiles are intentionally left alone.
    """
    destination = Path(output_path)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{destination.stem}.stage-", dir=destination.parent)
    )
    preserve_stage = False
    try:
        staged_path = staging_dir / destination.name
        yield staged_path

        if not staged_path.is_file():
            raise ExportError(
                "ERR_EXPORT_STAGE_INCOMPLETE",
                f"Export did not produce its primary output: {staged_path}",
            )

        staged_files = [file for file in staging_dir.iterdir() if file.is_file()]
        # Publish the VRT last, after all the referenced tiles and sidecars.
        # An already-open VRT can still observe intermediate tile updates.
        staged_files.sort(key=lambda file: (file == staged_path, file.name))
        backup_dir = staging_dir / ".backups"
        backup_dir.mkdir()
        backed_up: list[Path] = []
        published: list[Path] = []
        try:
            for source in staged_files:
                target = destination.parent / source.name
                if target.exists():
                    os.replace(target, backup_dir / source.name)
                    backed_up.append(target)
                os.replace(source, target)
                published.append(target)
        except Exception as publish_error:
            rollback_errors: list[Exception] = []
            for target in reversed(published):
                try:
                    target.unlink()
                except OSError as error:
                    rollback_errors.append(error)
            for target in reversed(backed_up):
                try:
                    os.replace(backup_dir / target.name, target)
                except OSError as error:
                    rollback_errors.append(error)

            if not rollback_errors:
                raise ExportError(
                    "ERR_EXPORT_PUBLISH_ROLLED_BACK",
                    (
                        f"Publishing '{destination}' failed: {publish_error}. "
                        "Previously existing output files were restored; "
                        "new files from this publication were removed."
                    ),
                ) from publish_error

            # Keep any remaining previous versions outside the temporary
            # directory so that normal cleanup cannot delete them.
            recovery_dir = destination.parent / (f".{destination.stem}.recovery-{uuid.uuid4().hex}")
            try:
                backup_dir.rename(recovery_dir)
            except OSError as recovery_error:
                # Keep the entire staging folder when its backup subfolder
                # cannot be moved. Never let automatic cleanup erase backups.
                preserve_stage = True
                raise ExportError(
                    "ERR_EXPORT_PUBLISH_RECOVERY_REQUIRED",
                    (
                        f"Publishing '{destination}' failed: {publish_error}. "
                        f"Rollback also failed: {rollback_errors!r}. "
                        f"Could not relocate backups: {recovery_error}. "
                        f"Recovery files remain in '{staging_dir}'. "
                        "Some target files may have changed. Inspect both "
                        "locations before retrying; do not delete backups."
                    ),
                ) from recovery_error

            raise ExportError(
                "ERR_EXPORT_PUBLISH_RECOVERY_REQUIRED",
                (
                    f"Publishing '{destination}' failed: {publish_error}. "
                    f"Rollback also failed: {rollback_errors!r}. "
                    f"Remaining backups were saved to '{recovery_dir}'. "
                    "Some target files may have changed. Inspect both "
                    "locations before retrying; do not delete recovery files."
                ),
            ) from publish_error

    finally:
        if not preserve_stage:
            shutil.rmtree(staging_dir)
