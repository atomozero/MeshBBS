"""
Lightweight schema migrations (no Alembic).

MIT License - Copyright (c) 2026 MeshBBS Contributors

Base.metadata.create_all() creates brand-new tables, but never alters
existing ones. Everything else (new columns, new indexes, data fixes on
existing databases) is done here by an ordered list of migrations.

- The applied versions are stored in the ``schema_version`` table
  (version, name, applied_at).
- Version 0 is the baseline (schema of v1.6.0): on a database without
  ``schema_version`` it only adds model columns that may be missing, so
  an existing database whose columns are all present is simply stamped.
- Every migration runs in its own transaction (BEGIN IMMEDIATE), together
  with the insert of its version row: it is either fully applied or not
  at all. Migrations are also written to be idempotent.
- run_migrations() is called by init_database() after create_all();
  a second run is a no-op.

To add a migration: write ``def _mNNNN_xxx(conn)`` (conn is a SQLAlchemy
Connection already inside the transaction; do not commit) and append it
to MIGRATIONS with the next version number. Never renumber or remove a
migration that has been released.
"""

import re
from datetime import datetime
from typing import Callable, List, NamedTuple, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.migrations")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.migrations")


SCHEMA_VERSION_TABLE = "schema_version"
BASELINE_VERSION = 0

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class Migration(NamedTuple):
    version: int
    name: str
    apply: Callable[[Connection], None]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_ident(name: str) -> str:
    if not _IDENT_RE.match(name or ""):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return name


def table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).first()
    return row is not None


def get_columns(conn: Connection, table: str) -> List[str]:
    """Column names of a table (empty list if the table does not exist)."""
    rows = conn.exec_driver_sql(f"PRAGMA table_info({_check_ident(table)})").fetchall()
    return [r[1] for r in rows]


def add_column_if_missing(conn: Connection, table: str, column_ddl: str) -> bool:
    """
    Add a column to an existing table unless it is already there.

    Args:
        conn: Connection (inside the migration transaction)
        table: Table name
        column_ddl: Column definition as in ALTER TABLE ... ADD COLUMN,
            e.g. "muted_until DATETIME" or "flags INTEGER NOT NULL DEFAULT 0"

    Returns:
        True if the column was added, False if it already existed
    """
    column = _check_ident(column_ddl.split()[0].strip('"'))
    if column in get_columns(conn, table):
        return False
    conn.exec_driver_sql(f"ALTER TABLE {_check_ident(table)} ADD COLUMN {column_ddl}")
    logger.info(f"Migration: added column {table}.{column}")
    return True


def _column_ddl(conn: Connection, column) -> Optional[str]:
    """
    Build an ADD COLUMN definition from a model Column, or None if SQLite
    cannot add it (NOT NULL without a usable default, primary key, unique).
    """
    if column.primary_key or column.unique:
        return None
    ddl = f"{column.name} {column.type.compile(dialect=conn.dialect)}"
    default = None
    if column.server_default is not None:
        default = getattr(column.server_default, "arg", None)
        default = getattr(default, "text", default)
    elif column.default is not None and getattr(column.default, "is_scalar", False):
        value = column.default.arg
        if isinstance(value, bool):
            default = "1" if value else "0"
        elif isinstance(value, (int, float)):
            default = str(value)
        elif isinstance(value, str):
            default = "'" + value.replace("'", "''") + "'"
    if not column.nullable:
        if default is None:
            return None
        ddl += " NOT NULL"
    if default is not None:
        ddl += f" DEFAULT {default}"
    return ddl


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------


def _m0000_baseline(conn: Connection) -> None:
    """Baseline 1.6.0: add any model column missing from existing tables."""
    from .base import Base

    missing = 0
    for table in Base.metadata.sorted_tables:
        present = get_columns(conn, table.name)
        if not present:
            continue  # table just created by create_all() or not ours
        for column in table.columns:
            if column.name in present:
                continue
            ddl = _column_ddl(conn, column)
            if ddl is None:
                logger.warning(
                    f"Migration: cannot add column {table.name}.{column.name} "
                    f"automatically (NOT NULL without default)"
                )
                continue
            add_column_if_missing(conn, table.name, ddl)
            missing += 1
    if missing:
        logger.info(f"Baseline: {missing} missing column(s) added")
    else:
        logger.info("Baseline: existing schema is complete")


def _m0001_normalize_user_keys(conn: Connection) -> None:
    """
    Users stored with a full 64-char key -> canonical 12-char prefix.

    Keys are canonicalised on input, so this one-shot data fix replaces the
    normalisation that used to run at every start. It runs before the
    nickname index: merging duplicate rows of the same person first avoids
    renaming the nick of what is really one user.
    """
    from bbs.services.user_keys import normalize_user_keys

    normalize_user_keys(conn, commit=False)


# Nick rules (see NickCommand / UserRepository)
NICK_MIN_LENGTH = 2
NICK_MAX_LENGTH = 16
_NICK_INVALID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


def _dedupe_candidate(base: str, n: int) -> str:
    suffix = f"_{n}"
    return base[: NICK_MAX_LENGTH - len(suffix)] + suffix


def resolve_duplicate_nicknames(conn: Connection) -> int:
    """
    Rename nicknames that collide case-insensitively.

    The oldest user (first_seen, then id) keeps the nick, the others get
    "<nick>_2", "<nick>_3", ... (truncated to 16 chars, only [A-Za-z0-9_-],
    unique case-insensitively). Each rename is logged and written to the
    activity log.

    Returns:
        Number of renamed users
    """
    rows = conn.execute(
        text(
            "SELECT id, public_key, nickname FROM users "
            "WHERE nickname IS NOT NULL ORDER BY first_seen, id"
        )
    ).fetchall()
    taken = {r[2].lower() for r in rows}
    seen = set()
    has_log = table_exists(conn, "activity_log")
    renamed = 0

    for user_id, public_key, nickname in rows:
        low = nickname.lower()
        if low not in seen:
            seen.add(low)
            continue

        base = _NICK_INVALID_CHARS.sub("", nickname) or "utente"
        n = 2
        candidate = _dedupe_candidate(base, n)
        while candidate.lower() in taken:
            n += 1
            candidate = _dedupe_candidate(base, n)
        taken.add(candidate.lower())
        seen.add(candidate.lower())

        conn.execute(
            text("UPDATE users SET nickname = :nick WHERE id = :id"),
            {"nick": candidate, "id": user_id},
        )
        if has_log:
            conn.execute(
                text(
                    "INSERT INTO activity_log (timestamp, event_type, user_key, details) "
                    "VALUES (:ts, 'user_nickname_set', :key, :details)"
                ),
                {
                    "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"),
                    "key": public_key,
                    "details": (
                        f"Nickname changed: {nickname} -> {candidate} "
                        f"(duplicate resolved by migration)"
                    ),
                },
            )
        logger.warning(
            f"Duplicate nickname: user {public_key[:12]} renamed "
            f"'{nickname}' -> '{candidate}'"
        )
        renamed += 1
    return renamed


def _m0002_unique_nickname_index(conn: Connection) -> None:
    """Unique case-insensitive nickname (duplicates renamed first)."""
    renamed = resolve_duplicate_nicknames(conn)
    if renamed:
        logger.info(f"Duplicate nicknames resolved: {renamed} user(s) renamed")
    conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_nickname_lower "
        "ON users(lower(nickname)) WHERE nickname IS NOT NULL"
    )


MIGRATIONS: List[Migration] = [
    Migration(0, "baseline 1.6.0", _m0000_baseline),
    Migration(1, "chiavi utente canoniche", _m0001_normalize_user_keys),
    Migration(2, "indice univoco nickname (case-insensitive)", _m0002_unique_nickname_index),
]

LATEST_VERSION = MIGRATIONS[-1].version


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def get_schema_version(conn: Connection) -> Optional[int]:
    """Highest applied version, or None if no migration was ever recorded."""
    if not table_exists(conn, SCHEMA_VERSION_TABLE):
        return None
    return conn.execute(text(f"SELECT MAX(version) FROM {SCHEMA_VERSION_TABLE}")).scalar()


def run_migrations(engine: Engine) -> List[int]:
    """
    Apply pending migrations, each in its own transaction.

    Returns:
        Versions applied by this call (empty if the schema is up to date)

    Raises:
        Exception: the failing migration's error (its transaction is rolled
            back, earlier migrations stay applied)
    """
    if engine.dialect.name != "sqlite":
        logger.warning("Schema migrations support SQLite only: skipped")
        return []

    applied: List[int] = []
    with engine.connect() as conn:
        # pysqlite does not open a transaction before DDL: take manual
        # control (BEGIN/COMMIT) so DDL and data changes are atomic.
        dbapi_conn = conn.connection.driver_connection
        saved_isolation = dbapi_conn.isolation_level
        dbapi_conn.isolation_level = None
        try:
            conn.exec_driver_sql(
                f"CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} ("
                "version INTEGER PRIMARY KEY, "
                "name VARCHAR(100) NOT NULL, "
                "applied_at DATETIME NOT NULL)"
            )
            current = get_schema_version(conn)
            conn.commit()

            for migration in MIGRATIONS:
                if current is not None and migration.version <= current:
                    continue
                logger.info(f"Schema migration {migration.version}: {migration.name}...")
                conn.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    migration.apply(conn)
                    conn.execute(
                        text(
                            f"INSERT INTO {SCHEMA_VERSION_TABLE} (version, name, applied_at) "
                            "VALUES (:v, :n, :t)"
                        ),
                        {
                            "v": migration.version,
                            "n": migration.name,
                            "t": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
                    conn.exec_driver_sql("COMMIT")
                except Exception:
                    conn.exec_driver_sql("ROLLBACK")
                    conn.rollback()
                    logger.error(f"Schema migration {migration.version} failed: rolled back")
                    raise
                conn.commit()  # sync SQLAlchemy state (no-op for the DB)
                applied.append(migration.version)
                logger.info(f"Schema migration {migration.version} applied")
        finally:
            dbapi_conn.isolation_level = saved_isolation

    if applied:
        logger.info(f"Database schema at version {applied[-1]}")
    return applied
