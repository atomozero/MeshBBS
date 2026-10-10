"""
Tests for the lightweight schema migrations (bbs.models.migrations).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import shutil
import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

import bbs.models.base as db_base
import bbs.models.migrations as migrations
from bbs.models.base import Base
from bbs.models.user import User
from bbs.repositories.user_repository import NicknameError, UserRepository


@pytest.fixture
def db_path(tmp_path):
    db_base._engine = None
    db_base._SessionFactory = None
    yield str(tmp_path / "bbs.db")
    if db_base._engine is not None:
        db_base._engine.dispose()
    db_base._engine = None
    db_base._SessionFactory = None


def _make_legacy_db(path, users=(), drop_columns=()):
    """
    Build a database as created by v1.6.0 (no schema_version table, no
    nickname index), optionally with users and with some columns missing.
    """
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    conn.execute("DROP INDEX ix_users_nickname_lower")
    for table, column in drop_columns:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
    for i, (key, nick) in enumerate(users):
        conn.execute(
            "INSERT INTO users (public_key, nickname, first_seen, is_admin, "
            "is_moderator, is_banned, is_muted) VALUES (?, ?, ?, 0, 0, 0, 0)",
            (key, nick, f"2026-01-{i + 1:02d} 10:00:00.000000"),
        )
    conn.commit()
    conn.close()


def _sql(path, query, params=()):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def _versions(path):
    return [r[0] for r in _sql(path, "SELECT version FROM schema_version ORDER BY version")]


def _has_nick_index(path):
    return bool(_sql(
        path,
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='ix_users_nickname_lower'",
    ))


ALL_VERSIONS = [m.version for m in migrations.MIGRATIONS]


class TestFreshDatabase:
    def test_fresh_db_reaches_latest_version(self, db_path):
        db_base.init_database(db_path)
        assert _versions(db_path) == ALL_VERSIONS
        assert ALL_VERSIONS[-1] == migrations.LATEST_VERSION
        assert _has_nick_index(db_path)

    def test_second_run_is_noop(self, db_path):
        db_base.init_database(db_path)
        assert migrations.run_migrations(db_base.get_engine()) == []
        db_base.init_database(db_path)
        assert _versions(db_path) == ALL_VERSIONS


class TestLegacyDatabase:
    def test_existing_db_is_stamped_and_migrated(self, db_path):
        _make_legacy_db(db_path, users=[("a" * 12, "alice")])
        db_base.init_database(db_path)
        assert _versions(db_path) == ALL_VERSIONS
        assert _has_nick_index(db_path)
        assert _sql(db_path, "SELECT nickname FROM users") == [("alice",)]

    def test_baseline_adds_missing_columns(self, db_path):
        _make_legacy_db(
            db_path,
            users=[("a" * 12, "alice")],
            drop_columns=[("users", "kick_reason"), ("delivery_statuses", "ack_rssi")],
        )
        db_base.init_database(db_path)
        cols = [r[1] for r in _sql(db_path, "PRAGMA table_info(users)")]
        assert "kick_reason" in cols
        cols = [r[1] for r in _sql(db_path, "PRAGMA table_info(delivery_statuses)")]
        assert "ack_rssi" in cols

    def test_full_keys_normalised_once(self, db_path):
        full = "ABCDEF0123456789" * 4
        _make_legacy_db(db_path, users=[(full, "bob")])
        db_base.init_database(db_path)
        assert _sql(db_path, "SELECT public_key, nickname FROM users") == [
            ("abcdef012345", "bob")
        ]

    def test_failed_migration_is_rolled_back(self, db_path, monkeypatch):
        db_base.init_database(db_path)

        def boom(conn):
            conn.exec_driver_sql("CREATE TABLE half_done (id INTEGER)")
            conn.exec_driver_sql("UPDATE users SET nickname = 'x'")
            raise RuntimeError("boom")

        monkeypatch.setattr(
            migrations,
            "MIGRATIONS",
            migrations.MIGRATIONS + [migrations.Migration(99, "boom", boom)],
        )
        with pytest.raises(RuntimeError):
            migrations.run_migrations(db_base.get_engine())
        assert 99 not in _versions(db_path)
        assert not _sql(db_path, "SELECT 1 FROM sqlite_master WHERE name='half_done'")


class TestDuplicateNicknames:
    def test_duplicates_renamed_oldest_keeps_nick(self, db_path):
        _make_legacy_db(db_path, users=[
            ("a" * 12, "Mario"),      # oldest: keeps the nick
            ("b" * 12, "mario"),
            ("c" * 12, "MARIO"),
            ("d" * 12, "mario_2"),    # already taken suffix
            ("e" * 12, None),
            ("f" * 12, None),
        ])
        db_base.init_database(db_path)
        nicks = dict(_sql(db_path, "SELECT public_key, nickname FROM users"))
        assert nicks["a" * 12] == "Mario"
        assert nicks["d" * 12] == "mario_2"
        assert nicks["b" * 12] == "mario_3"
        assert nicks["c" * 12] == "MARIO_4"
        assert nicks["e" * 12] is None and nicks["f" * 12] is None
        logs = _sql(
            db_path,
            "SELECT user_key FROM activity_log WHERE event_type='user_nickname_set'",
        )
        assert sorted(r[0] for r in logs) == ["b" * 12, "c" * 12]

    def test_renamed_nick_respects_rules(self, db_path):
        _make_legacy_db(db_path, users=[
            ("a" * 12, "abcdefghijklmnop"),   # 16 chars, max length
            ("b" * 12, "ABCDEFGHIJKLMNOP"),
        ])
        db_base.init_database(db_path)
        new = _sql(db_path, "SELECT nickname FROM users WHERE public_key=?", ("b" * 12,))[0][0]
        assert new == "ABCDEFGHIJKLMN_2"
        assert len(new) <= 16

    def test_unique_index_enforced(self, db_path):
        db_base.init_database(db_path)
        with db_base.get_session() as session:
            session.add(User(public_key="a" * 12, nickname="Luigi"))
            session.add(User(public_key="b" * 12))
            session.add(User(public_key="c" * 12))  # many NULL nicks allowed
        with pytest.raises(IntegrityError):
            with db_base.get_session() as session:
                session.add(User(public_key="d" * 12, nickname="LUIGI"))

    def test_set_nickname_race_raises_nickname_error(self, db_path, monkeypatch):
        db_base.init_database(db_path)
        with db_base.get_session() as session:
            session.add(User(public_key="a" * 12, nickname="Luigi"))
            session.add(User(public_key="b" * 12, nickname="old"))

        # Simulate a concurrent writer: the pre-check sees the nick as free
        monkeypatch.setattr(UserRepository, "is_nickname_taken", lambda *a, **k: False)
        with db_base.get_session() as session:
            repo = UserRepository(session)
            with pytest.raises(NicknameError):
                repo.set_nickname("b" * 12, "luigi")
            # The session is still usable and the old nick is kept
            assert repo.get_by_public_key("b" * 12).nickname == "old"
            assert repo.set_nickname("b" * 12, "nuovo").nickname == "nuovo"
        assert _sql(db_path, "SELECT nickname FROM users WHERE public_key=?", ("b" * 12,)) == [
            ("nuovo",)
        ]


class TestHelpers:
    def test_add_column_if_missing(self, db_path):
        db_base.init_database(db_path)
        engine = db_base.get_engine()
        with engine.begin() as conn:
            assert migrations.add_column_if_missing(conn, "users", "extra_flag INTEGER NOT NULL DEFAULT 0")
            assert not migrations.add_column_if_missing(conn, "users", "extra_flag INTEGER")
        assert "extra_flag" in [r[1] for r in _sql(db_path, "PRAGMA table_info(users)")]

    def test_add_column_rejects_bad_identifiers(self, db_path):
        db_base.init_database(db_path)
        with db_base.get_engine().begin() as conn:
            with pytest.raises(ValueError):
                migrations.add_column_if_missing(conn, "users; DROP TABLE users", "x INTEGER")


@pytest.mark.skipif(
    not os.environ.get("MESHBBS_TEST_DB"),
    reason="set MESHBBS_TEST_DB to a copy of a real database to run",
)
def test_real_database_copy(db_path):
    """Migrate a copy of a real database (never the original)."""
    shutil.copy(os.environ["MESHBBS_TEST_DB"], db_path)
    before = _sql(db_path, "SELECT COUNT(*) FROM messages")[0][0]
    db_base.init_database(db_path)
    assert _versions(db_path) == ALL_VERSIONS
    assert _has_nick_index(db_path)
    assert _sql(db_path, "PRAGMA integrity_check") == [("ok",)]
    assert _sql(db_path, "PRAGMA foreign_key_check") == []
    assert _sql(db_path, "SELECT COUNT(*) FROM messages")[0][0] == before
    assert not _sql(
        db_path,
        "SELECT 1 FROM users WHERE length(public_key) > 12 "
        "AND public_key NOT GLOB '*[^0-9a-fA-F]*'",
    )
    assert migrations.run_migrations(db_base.get_engine()) == []
