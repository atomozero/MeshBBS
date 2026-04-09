"""
Backup management for MeshBBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors

This module provides automatic and manual backup functionality for the
MeshBBS database and configuration files.
"""

import asyncio
import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.backup")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.backup")


class BackupManager:
    """
    Manages database backups for MeshBBS.

    Supports automatic scheduled backups, manual backups, and backup rotation.
    """

    def __init__(
        self,
        database_path: str,
        backup_dir: str,
        max_backups: int = 7,
        compress: bool = True,
    ):
        """
        Initialize backup manager.

        Args:
            database_path: Path to the SQLite database file
            backup_dir: Directory to store backups
            max_backups: Maximum number of backups to keep
            compress: Whether to compress backups with gzip
        """
        self.database_path = Path(database_path)
        self.backup_dir = Path(backup_dir)
        self.max_backups = max_backups
        self.compress = compress

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Background task handle
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False

    def create_backup(self, label: str = "") -> Optional[Path]:
        """
        Create a backup of the database.

        Args:
            label: Optional label to include in backup filename

        Returns:
            Path to created backup file or None on failure
        """
        if not self.database_path.exists():
            logger.error(f"Database file not found: {self.database_path}")
            return None

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        label_part = f"-{label}" if label else ""
        ext = ".db.gz" if self.compress else ".db"
        backup_name = f"meshbbs-backup{label_part}-{timestamp}{ext}"
        backup_path = self.backup_dir / backup_name

        try:
            if self.compress:
                # Compressed backup
                with open(self.database_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Simple copy
                shutil.copy2(self.database_path, backup_path)

            logger.info(f"Backup created: {backup_path}")

            # Rotate old backups
            self._rotate_backups()

            return backup_path

        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    def restore_backup(self, backup_path: str) -> bool:
        """
        Restore database from a backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if restore successful
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            return False

        try:
            # Create safety backup of current database
            if self.database_path.exists():
                safety_backup = self.database_path.with_suffix('.db.pre-restore')
                shutil.copy2(self.database_path, safety_backup)
                logger.info(f"Safety backup created: {safety_backup}")

            # Restore
            if backup_file.suffix == '.gz':
                # Decompress and restore
                with gzip.open(backup_file, 'rb') as f_in:
                    with open(self.database_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Simple copy
                shutil.copy2(backup_file, self.database_path)

            logger.info(f"Database restored from: {backup_file}")
            return True

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False

    def list_backups(self) -> List[dict]:
        """
        List all available backups.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        for f in self.backup_dir.iterdir():
            if f.is_file() and f.name.startswith('meshbbs-backup'):
                stat = f.stat()
                backups.append({
                    'name': f.name,
                    'path': str(f),
                    'size': stat.st_size,
                    'size_human': self._format_size(stat.st_size),
                    'created_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'compressed': f.suffix == '.gz',
                })

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups

    def delete_backup(self, backup_name: str) -> bool:
        """
        Delete a specific backup.

        Args:
            backup_name: Name of backup file to delete

        Returns:
            True if deletion successful
        """
        backup_path = self.backup_dir / backup_name

        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_name}")
            return False

        if not backup_name.startswith('meshbbs-backup'):
            logger.error(f"Invalid backup filename: {backup_name}")
            return False

        try:
            backup_path.unlink()
            logger.info(f"Backup deleted: {backup_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def _rotate_backups(self) -> None:
        """Remove old backups exceeding max_backups limit."""
        backups = self.list_backups()

        if len(backups) > self.max_backups:
            # Delete oldest backups
            for backup in backups[self.max_backups:]:
                try:
                    Path(backup['path']).unlink()
                    logger.info(f"Rotated old backup: {backup['name']}")
                except Exception as e:
                    logger.error(f"Failed to rotate backup: {e}")

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    async def start_scheduler(self, interval_hours: int = 24) -> None:
        """
        Start automatic backup scheduler.

        Args:
            interval_hours: Hours between automatic backups
        """
        if self._running:
            logger.warning("Backup scheduler already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(
            self._scheduler_loop(interval_hours)
        )
        logger.info(f"Backup scheduler started (every {interval_hours}h)")

    async def stop_scheduler(self) -> None:
        """Stop the automatic backup scheduler."""
        self._running = False

        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
            self._scheduler_task = None

        logger.info("Backup scheduler stopped")

    async def _scheduler_loop(self, interval_hours: int) -> None:
        """Background task for scheduled backups."""
        interval_seconds = interval_hours * 3600

        while self._running:
            try:
                await asyncio.sleep(interval_seconds)

                if self._running:
                    logger.info("Running scheduled backup...")
                    backup_path = self.create_backup(label="auto")

                    if backup_path:
                        logger.info(f"Scheduled backup completed: {backup_path}")
                    else:
                        logger.error("Scheduled backup failed")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in backup scheduler: {e}")
                await asyncio.sleep(60)  # Wait before retry


class BackupConfig:
    """Configuration for backup settings."""

    def __init__(
        self,
        enabled: bool = True,
        interval_hours: int = 24,
        max_backups: int = 7,
        compress: bool = True,
        backup_dir: str = "/var/lib/meshbbs/backups",
    ):
        self.enabled = enabled
        self.interval_hours = interval_hours
        self.max_backups = max_backups
        self.compress = compress
        self.backup_dir = backup_dir

    @classmethod
    def from_env(cls) -> 'BackupConfig':
        """Create config from environment variables."""
        return cls(
            enabled=os.getenv('BACKUP_ENABLED', 'true').lower() == 'true',
            interval_hours=int(os.getenv('BACKUP_INTERVAL_HOURS', '24')),
            max_backups=int(os.getenv('BACKUP_MAX_COUNT', '7')),
            compress=os.getenv('BACKUP_COMPRESS', 'true').lower() == 'true',
            backup_dir=os.getenv('BACKUP_PATH', '/var/lib/meshbbs/backups'),
        )
