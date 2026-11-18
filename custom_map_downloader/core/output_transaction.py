"""Stage raster output beside the destination; publish only on success.

One file can be replaced atomically on a single filesystem. A VRT with its
tiles and sidecars is a multi-file set: rollback is supported, but publication
cannot be atomic as a whole using ordinary filesystem operations.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def staged_raster_output(output_path: str | Path) -> Iterator[Path]:
    """Stage outputs in the target directory and publish on clean exit.

    Before replacing a destination, its original file is backed up using a
    same-filesystem rename. If publishing fails, newly installed files are
    removed and the previous files are restored. Unrelated and obsolete VRT
    tiles are intentionally left alone.
    """
    destination = Path(output_path)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.stem}.stage-", dir=destination.parent
    ) as directory:
        staging_dir = Path(directory)
        staged_path = staging_dir / destination.name
        yield staged_path

        if not staged_path.is_file():
            raise RuntimeError(f"Export did not produce its primary output: {staged_path}")

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
        except Exception:
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
            if rollback_errors:
                # Never destroy remaining backups during temporary-dir cleanup
                # if the OS or antivirus locks a destination on Windows.
                recovery_dir = destination.parent / (
                    f".{destination.stem}.recovery-{uuid.uuid4().hex}"
                )
                try:
                    backup_dir.rename(recovery_dir)
                except OSError as recovery_error:
                    raise RuntimeError(
                        "Publication and rollback failed; unable to preserve recovery files"
                    ) from recovery_error
                raise RuntimeError(
                    f"Publication and rollback failed; remaining backups: {recovery_dir}"
                ) from rollback_errors[0]
            raise
