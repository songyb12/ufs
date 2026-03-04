"""SQLite database backup utility.

Creates timestamped copies of the SQLite DB file.
Old backups are automatically cleaned up.
"""

import logging
import os
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("vibe.backup")


async def backup_database(db_path: str, backup_dir: str, keep_days: int = 7) -> str | None:
    """Create a backup of the SQLite database using SQLite Online Backup API.

    Returns the backup file path on success, None on failure.
    """
    import asyncio

    def _do_backup():
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"vibe_{timestamp}.db"

            # Use SQLite Online Backup API (safe for concurrent access)
            source = sqlite3.connect(db_path)
            dest = sqlite3.connect(str(backup_file))
            try:
                source.backup(dest)
                logger.info("DB backup created: %s", backup_file.name)
            finally:
                dest.close()
                source.close()

            # Get backup file size
            size_mb = backup_file.stat().st_size / (1024 * 1024)
            logger.info("Backup size: %.2f MB", size_mb)

            # Cleanup old backups
            _cleanup_old_backups(backup_path, keep_days)

            return str(backup_file)

        except Exception as e:
            logger.exception("DB backup failed: %s", e)
            return None

    return await asyncio.to_thread(_do_backup)


def _cleanup_old_backups(backup_dir: Path, keep_days: int) -> int:
    """Remove backup files older than keep_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    removed = 0

    for f in backup_dir.glob("vibe_*.db"):
        try:
            # Parse timestamp from filename: vibe_YYYYMMDD_HHMMSS.db
            name_parts = f.stem.split("_", 1)
            if len(name_parts) < 2:
                continue
            file_time = datetime.strptime(name_parts[1], "%Y%m%d_%H%M%S").replace(
                tzinfo=timezone.utc
            )
            if file_time < cutoff:
                f.unlink()
                removed += 1
                logger.info("Removed old backup: %s", f.name)
        except (ValueError, OSError) as e:
            logger.warning("Could not process backup file %s: %s", f.name, e)

    if removed:
        logger.info("Cleaned up %d old backup(s)", removed)
    return removed
