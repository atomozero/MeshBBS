"""
SQLite tuning for SD-card based systems (Raspberry Pi).

MIT License - Copyright (c) 2026 MeshBBS Contributors

- Every new SQLite connection gets a bounded WAL file
  (journal_size_limit), synchronous=NORMAL (safe with WAL) and in-memory
  temp tables: fewer and smaller writes on the SD card.
- checkpoint() truncates the WAL file; the BBS runs it hourly and
  after each backup so the -wal file never stays large.

The listener is registered on the Engine class at import time (this
module is imported by the bbs.models package), so it applies to the
engine created later by base.get_engine() without touching it.
"""

import asyncio
import logging
import sqlite3
from typing import Optional, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("meshbbs.db")

# Max size the WAL file is truncated back to after a checkpoint
JOURNAL_SIZE_LIMIT = 1024 * 1024  # 1 MB

# How often the periodic WAL checkpoint runs
CHECKPOINT_INTERVAL = 3600  # 1 hour

TUNING_PRAGMAS = (
    f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT}",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA temp_store=MEMORY",
)


def apply_pragmas(dbapi_connection) -> None:
    """Apply the SD-friendly pragmas to a raw sqlite3 connection."""
    cursor = dbapi_connection.cursor()
    try:
        for pragma in TUNING_PRAGMAS:
            cursor.execute(pragma)
    finally:
        cursor.close()


@event.listens_for(Engine, "connect")
def _tune_sqlite_connection(dbapi_connection, connection_record):
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return  # another DB backend: nothing to do
    try:
        apply_pragmas(dbapi_connection)
    except Exception as e:  # never break a connection for a tuning pragma
        logger.warning(f"SQLite tuning pragmas failed: {e}")


def checkpoint(engine: Optional[Engine] = None) -> Optional[Tuple[int, int, int]]:
    """
    Run PRAGMA wal_checkpoint(TRUNCATE) on the BBS database.

    Returns:
        (busy, wal_frames, checkpointed_frames), or None if no engine
    """
    if engine is None:
        from bbs.models import base
        engine = base._engine
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    return tuple(row) if row else None


async def periodic_checkpoint(interval: float = CHECKPOINT_INTERVAL) -> None:
    """Checkpoint the WAL every `interval` seconds (runs in a worker thread)."""
    while True:
        await asyncio.sleep(interval)
        try:
            result = await asyncio.to_thread(checkpoint)
            logger.debug(f"WAL checkpoint: {result}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"WAL checkpoint failed: {e}")
