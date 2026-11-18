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
from typing import Callable, Iterator

from .errors import ExportError


def should_use_local_work(
    destination: str | Path, slow_device: Callable[[str], bool]
) -> bool:
    """Prefer a fast user temp when target is slow or shares temp's device.

    QgsFileUtils.pathIsSlowDevice is injected by the QGIS exporter so this
    filesystem module remains usable in Python-only tests.
    """
    target_dir = Path(destination).parent
    temp_dir = Path(tempfile.gettempdir())
    try:
        if slow_device(str(temp_dir)):
            return False
        return slow_device(str(target_dir)) or temp_dir.stat().st_dev == target_dir.stat().st_dev
    except (OSError, RuntimeError, ValueError):
        # Unsupported path/device information must not disable safe exporting.
        return False


def transfer_finished_files(
    source_dir: Path,
    target_dir: Path,
    check_cancel: Callable[[], None] | None = None,
) -> None:
    """Transfer completed files into target-side staging, never the final target.

    Use same-filesystem rename where possible and chunked standard-library
    reads/writes for cross-filesystem copies, allowing cancellation between
    chunks. Partial copies remain isolated within staging.
    """
    if source_dir == target_dir:
        return

    same_device = source_dir.stat().st_dev == target_dir.stat().st_dev
    for source in source_dir.iterdir():
        if not source.is_file():
            continue
        if check_cancel is not None:
            check_cancel()
        staged = target_dir / source.name
        if same_device:
            try:
                os.replace(source, staged)
                continue
            except OSError:
                # Device IDs can be misleading on mounted/virtual filesystems.
                # A conventional copy is still safe inside target-side staging.
                pass
        try:
            with source.open("rb") as reader, staged.open("xb") as writer:
                while True:
                    if check_cancel is not None:
                        check_cancel()
                    chunk = reader.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    writer.write(chunk)
            shutil.copystat(source, staged)
            if staged.stat().st_size != source.stat().st_size:
                raise OSError(f"Copied file size mismatch: {source.name}")
        except Exception:
            staged.unlink(missing_ok=True)
            raise


def create_local_work_directory(
    prefer_local: bool, *, estimated_bytes: int = 0
) -> Path | None:
    """Use local user temp only if it is writable and has basic free capacity."""
    if not prefer_local:
        return None
    temp_root = Path(tempfile.gettempdir())
    try:
        # The estimate may be conservative/approximate; retain headroom.
        reserve = 128 * 1024 * 1024
        if shutil.disk_usage(temp_root).free < max(estimated_bytes, 0) + reserve:
            return None
        return Path(tempfile.mkdtemp(prefix="cmd-work-", dir=temp_root))
    except OSError:
        # Fall back before rendering; never switch workspace mid-export.
        return None


@contextmanager
def staged_raster_output(
    output_path: str | Path,
    *,
    prefer_local: bool = False,
    estimated_bytes: int = 0,
    check_cancel: Callable[[], None] | None = None,
) -> Iterator[Path]:
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
    work_dir = create_local_work_directory(prefer_local, estimated_bytes=estimated_bytes)
    try:
        staged_path = (work_dir or staging_dir) / destination.name
        yield staged_path

        if not staged_path.is_file():
            raise ExportError(
                "ERR_EXPORT_STAGE_INCOMPLETE",
                f"Export did not produce its primary output: {staged_path}",
            )

        if work_dir is not None:
            try:
                transfer_finished_files(work_dir, staging_dir, check_cancel)
            except Exception as error:
                from .errors import CancelledError

                if isinstance(error, CancelledError):
                    raise
                raise ExportError(
                    "ERR_EXPORT_TRANSFER_FAILED",
                    f"Could not transfer completed output into target staging: {error}",
                ) from error

        staged_files = [file for file in staging_dir.iterdir() if file.is_file()]
        # Publish the VRT last, after all the referenced tiles and sidecars.
        # An already-open VRT can still observe intermediate tile updates.
        staged_files.sort(key=lambda file: (file.name == destination.name, file.name))
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
        if work_dir is not None:
            shutil.rmtree(work_dir)
        if not preserve_stage:
            shutil.rmtree(staging_dir)
