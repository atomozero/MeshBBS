"""
Automatic database backups.

MIT License - Copyright (c) 2026 MeshBBS Contributors

A consistent online copy is taken with the sqlite3 backup API (safe while
the BBS writes, WAL included), checked with PRAGMA quick_check, gzipped
to <BACKUP_DIR>/meshbbs-YYYYmmdd-HHMMSS.db.gz and rotated (BACKUP_KEEP
newest kept). The nightly run happens at BACKUP_TIME (local time) in a
worker thread, so the asyncio loop is never blocked.

Environment:
    BACKUP_ENABLED  true      nightly backup on/off
    BACKUP_TIME     03:30     local time (HH:MM)
    BACKUP_DIR      <db dir>/backups
    BACKUP_KEEP     7         number of backups kept
"""

import asyncio
import gzip
import os
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.backup")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.backup")

BACKUP_PREFIX = "meshbbs-"
BACKUP_SUFFIX = ".db.gz"

# One backup at a time (nightly task and the web "backup now" button)
_backup_lock = threading.Lock()


def _parse_time(value: str) -> Tuple[int, int]:
    try:
        hh, mm = value.strip().split(":", 1)
        hour, minute = int(hh), int(mm)
        if 0 <= hour < 24 and 0 <= minute < 60:
            return hour, minute
    except (ValueError, AttributeError):
        pass
    logger.warning(f"Invalid BACKUP_TIME '{value}', using 03:30")
    return 3, 30


@dataclass
class BackupSettings:
    enabled: bool = True
    hour: int = 3
    minute: int = 30
    backup_dir: str = "backups"
    keep: int = 7

    @classmethod
    def from_env(cls, database_path: str) -> "BackupSettings":
        enabled = (os.getenv("BACKUP_ENABLED") or "true").strip().lower() in ("1", "true", "yes", "on")
        hour, minute = _parse_time(os.getenv("BACKUP_TIME") or "03:30")
        default_dir = str(Path(database_path).resolve().parent / "backups")
        try:
            keep = max(1, int(os.getenv("BACKUP_KEEP") or 7))
        except ValueError:
            keep = 7
        return cls(
            enabled=enabled,
            hour=hour,
            minute=minute,
            backup_dir=(os.getenv("BACKUP_DIR") or "").strip() or default_dir,
            keep=keep,
        )


@dataclass
class BackupResult:
    ok: bool
    path: Optional[str] = None
    size: int = 0
    created_at: Optional[datetime] = None
    error: Optional[str] = None
    duration: float = 0.0


def list_backups(backup_dir: str) -> List[Path]:
    """Backup files in backup_dir, newest first (names embed the timestamp)."""
    d = Path(backup_dir)
    if not d.is_dir():
        return []
    files = [
        f for f in d.iterdir()
        if f.is_file() and f.name.startswith(BACKUP_PREFIX) and f.name.endswith(BACKUP_SUFFIX)
    ]
    return sorted(files, key=lambda f: f.name, reverse=True)


def rotate_backups(backup_dir: str, keep: int) -> int:
    """Delete backups beyond the newest `keep`. Returns how many were removed."""
    removed = 0
    for old in list_backups(backup_dir)[max(1, keep):]:
        try:
            old.unlink()
            removed += 1
        except OSError as e:
            logger.warning(f"Cannot remove old backup {old.name}: {e}")
    return removed


def _cleanup_partials(backup_dir: Path) -> None:
    for f in backup_dir.glob(f"{BACKUP_PREFIX}*.part"):
        try:
            f.unlink()
        except OSError:
            pass


def create_backup(database_path: str, backup_dir: str, keep: int = 7) -> BackupResult:
    """
    Take a consistent, compressed backup of the SQLite database (blocking).

    Never raises: errors are returned in BackupResult.error.
    """
    started = datetime.now()
    if not _backup_lock.acquire(blocking=False):
        return BackupResult(ok=False, error="backup gia in corso")
    tmp_db: Optional[Path] = None
    part: Optional[Path] = None
    try:
        src_path = Path(database_path)
        if not src_path.is_file():
            return BackupResult(ok=False, error=f"database non trovato: {database_path}")

        out_dir = Path(backup_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        _cleanup_partials(out_dir)

        stamp = started.strftime("%Y%m%d-%H%M%S")
        final = out_dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}"
        tmp_db = out_dir / f"{BACKUP_PREFIX}{stamp}.db.part"
        part = out_dir / f"{BACKUP_PREFIX}{stamp}{BACKUP_SUFFIX}.part"

        # 1. Online consistent copy (sqlite3 backup API, WAL aware)
        src = sqlite3.connect(str(src_path), timeout=30)
        try:
            dst = sqlite3.connect(str(tmp_db))
            try:
                src.backup(dst, pages=1024, sleep=0.05)
                check = dst.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError(f"quick_check fallito: {check[0] if check else '?'}")
                # Self-contained single file (no -wal/-shm next to it)
                dst.execute("PRAGMA journal_mode=DELETE")
            finally:
                dst.close()
        finally:
            src.close()

        # 2. Compress, then atomically publish the file
        with open(tmp_db, "rb") as f_in, gzip.open(part, "wb", compresslevel=6) as f_out:
            shutil.copyfileobj(f_in, f_out, length=256 * 1024)
        os.replace(part, final)
        part = None

        rotate_backups(str(out_dir), keep)
        size = final.stat().st_size
        duration = (datetime.now() - started).total_seconds()
        return BackupResult(ok=True, path=str(final), size=size,
                            created_at=started, duration=duration)
    except Exception as e:
        return BackupResult(ok=False, error=str(e) or type(e).__name__, created_at=started)
    finally:
        for leftover in (tmp_db, part):
            if leftover is not None:
                try:
                    leftover.unlink()
                except OSError:
                    pass
        _backup_lock.release()


def run_backup(database_path: str, settings: Optional[BackupSettings] = None,
               reason: str = "manuale") -> BackupResult:
    """create_backup + logging + WAL checkpoint (blocking; use a thread)."""
    settings = settings or BackupSettings.from_env(database_path)
    result = create_backup(database_path, settings.backup_dir, settings.keep)
    if result.ok:
        logger.info(
            f"Backup {reason} completato: {Path(result.path).name} "
            f"({result.size // 1024} KB, {result.duration:.1f}s)"
        )
        try:
            from bbs.models.sqlite_tuning import checkpoint
            checkpoint()
        except Exception as e:
            logger.debug(f"WAL checkpoint after backup failed: {e}")
    else:
        logger.error(f"Backup {reason} fallito: {result.error}")
    _record_result(result)
    return result


# Last result in this process (the web page also reads the files on disk)
_last_result: Optional[BackupResult] = None


def _record_result(result: BackupResult) -> None:
    global _last_result
    _last_result = result


def backup_status(database_path: str) -> dict:
    """Summary for the web dashboard: last backup on disk + last error."""
    settings = BackupSettings.from_env(database_path)
    files = list_backups(settings.backup_dir)
    status = {
        "enabled": settings.enabled,
        "schedule": f"{settings.hour:02d}:{settings.minute:02d}",
        "backup_dir": settings.backup_dir,
        "keep": settings.keep,
        "count": len(files),
        "last_name": None,
        "last_time": None,
        "last_size": None,
        "last_error": None,
    }
    if files:
        latest = files[0]
        try:
            st = latest.stat()
            status["last_name"] = latest.name
            status["last_time"] = datetime.fromtimestamp(st.st_mtime)
            status["last_size"] = st.st_size
        except OSError:
            pass
    if _last_result is not None and not _last_result.ok:
        status["last_error"] = _last_result.error
    return status


def seconds_until(hour: int, minute: int, now: Optional[datetime] = None) -> float:
    """Seconds from `now` (local time) to the next HH:MM."""
    now = now or datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def nightly_backup_loop(database_path: str, settings: Optional[BackupSettings] = None) -> None:
    """Run the backup every day at the configured local time."""
    settings = settings or BackupSettings.from_env(database_path)
    if not settings.enabled:
        logger.info("Backup automatico disabilitato (BACKUP_ENABLED=false)")
        return
    logger.info(
        f"Backup automatico alle {settings.hour:02d}:{settings.minute:02d} "
        f"in {settings.backup_dir} (ne conservo {settings.keep})"
    )
    while True:
        # Re-evaluated every day: robust to clock changes (NTP, DST)
        await asyncio.sleep(seconds_until(settings.hour, settings.minute))
        try:
            await asyncio.to_thread(run_backup, database_path, settings, "notturno")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # pragma: no cover - run_backup never raises
            logger.error(f"Backup notturno: errore inatteso: {e}")
        await asyncio.sleep(61)  # never twice in the same minute
