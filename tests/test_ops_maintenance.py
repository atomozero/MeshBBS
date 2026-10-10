"""
Tests for node maintenance: DB backups, SQLite tuning (SD card), battery
estimate and node status, web backup button.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import gzip
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, text

import bbs.services.backup as backup_mod
from bbs.models import sqlite_tuning
from bbs.services.backup import (
    BackupSettings,
    backup_status,
    create_backup,
    list_backups,
    rotate_backups,
    run_backup,
    seconds_until,
)
from meshbbs_radio.state import MeshCoreStateManager, lipo_percent


def make_db(path: Path, rows: int = 50) -> None:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO t (v) VALUES (?)", [(f"row{i}",) for i in range(rows)])
    con.commit()
    con.close()


def restore(gz: Path, dest: Path) -> sqlite3.Connection:
    dest.write_bytes(gzip.decompress(gz.read_bytes()))
    return sqlite3.connect(str(dest))


# ---------------------------------------------------------------
# Backup
# ---------------------------------------------------------------

class TestBackup:
    def test_creates_consistent_gzip_copy(self, tmp_path):
        db = tmp_path / "bbs.db"
        make_db(db)
        # Uncheckpointed data still in the WAL must be in the backup
        live = sqlite3.connect(str(db))
        live.execute("INSERT INTO t (v) VALUES ('only-in-wal')")
        live.commit()

        result = create_backup(str(db), str(tmp_path / "backups"), keep=7)
        live.close()

        assert result.ok, result.error
        out = Path(result.path)
        assert out.name.startswith("meshbbs-") and out.name.endswith(".db.gz")
        assert result.size == out.stat().st_size > 0
        con = restore(out, tmp_path / "restored.db")
        assert con.execute("SELECT count(*) FROM t").fetchone()[0] == 51
        assert con.execute("SELECT v FROM t WHERE v='only-in-wal'").fetchone()
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        con.close()
        # no temp files left behind
        assert [p.name for p in (tmp_path / "backups").iterdir()] == [out.name]

    def test_rotation_keeps_newest(self, tmp_path):
        d = tmp_path / "b"
        d.mkdir()
        names = [f"meshbbs-2026010{i}-033000.db.gz" for i in range(1, 6)]
        for n in names:
            (d / n).write_bytes(b"x")
        (d / "other.txt").write_text("keep me")
        assert rotate_backups(str(d), 3) == 2
        left = sorted(p.name for p in d.iterdir())
        assert left == sorted(names[2:] + ["other.txt"])
        assert [p.name for p in list_backups(str(d))] == sorted(names[2:], reverse=True)

    def test_backup_rotates(self, tmp_path):
        db = tmp_path / "bbs.db"
        make_db(db, rows=5)
        d = tmp_path / "b"
        d.mkdir()
        for i in range(1, 4):
            (d / f"meshbbs-2020010{i}-000000.db.gz").write_bytes(b"old")
        result = create_backup(str(db), str(d), keep=2)
        assert result.ok
        files = list_backups(str(d))
        assert len(files) == 2
        assert files[0].name == Path(result.path).name

    def test_missing_database(self, tmp_path):
        result = create_backup(str(tmp_path / "nope.db"), str(tmp_path / "b"))
        assert not result.ok and "non trovato" in result.error

    def test_corrupt_database_reported(self, tmp_path):
        db = tmp_path / "bad.db"
        db.write_bytes(b"not a database" * 100)
        result = create_backup(str(db), str(tmp_path / "b"))
        assert not result.ok
        assert list_backups(str(tmp_path / "b")) == []
        assert not any((tmp_path / "b").glob("*.part"))

    def test_concurrent_backup_refused(self, tmp_path):
        db = tmp_path / "bbs.db"
        make_db(db, rows=1)
        assert backup_mod._backup_lock.acquire(blocking=False)
        try:
            result = create_backup(str(db), str(tmp_path / "b"))
        finally:
            backup_mod._backup_lock.release()
        assert not result.ok and "in corso" in result.error

    def test_settings_from_env(self, tmp_path, monkeypatch):
        db = tmp_path / "data" / "meshbbs.db"
        for k in ("BACKUP_ENABLED", "BACKUP_DIR", "BACKUP_KEEP", "BACKUP_TIME"):
            monkeypatch.delenv(k, raising=False)
        s = BackupSettings.from_env(str(db))
        assert s.enabled and (s.hour, s.minute) == (3, 30) and s.keep == 7
        assert s.backup_dir == str((tmp_path / "data" / "backups").resolve())
        monkeypatch.setenv("BACKUP_ENABLED", "false")
        monkeypatch.setenv("BACKUP_DIR", "/srv/bk")
        monkeypatch.setenv("BACKUP_KEEP", "3")
        monkeypatch.setenv("BACKUP_TIME", "04:15")
        s = BackupSettings.from_env(str(db))
        assert not s.enabled and s.backup_dir == "/srv/bk" and s.keep == 3
        assert (s.hour, s.minute) == (4, 15)
        monkeypatch.setenv("BACKUP_TIME", "25:99")
        monkeypatch.setenv("BACKUP_KEEP", "x")
        s = BackupSettings.from_env(str(db))
        assert (s.hour, s.minute) == (3, 30) and s.keep == 7

    def test_seconds_until(self):
        now = datetime(2026, 1, 1, 3, 0, 0)
        assert seconds_until(3, 30, now) == 1800
        assert seconds_until(3, 0, now) == 86400  # just passed: tomorrow
        assert seconds_until(2, 0, now) == 23 * 3600

    def test_run_backup_and_status(self, tmp_path, monkeypatch):
        db = tmp_path / "bbs.db"
        make_db(db, rows=3)
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "b"))
        monkeypatch.delenv("BACKUP_ENABLED", raising=False)
        st = backup_status(str(db))
        assert st["count"] == 0 and st["last_time"] is None
        result = run_backup(str(db))
        assert result.ok
        st = backup_status(str(db))
        assert st["count"] == 1 and st["last_size"] == result.size
        assert st["last_name"] == Path(result.path).name
        assert st["schedule"] == "03:30" and st["last_error"] is None

    @pytest.mark.asyncio
    async def test_nightly_loop_disabled(self, tmp_path):
        s = BackupSettings(enabled=False)
        await asyncio.wait_for(backup_mod.nightly_backup_loop("x.db", s), 1)

    @pytest.mark.asyncio
    async def test_nightly_loop_runs_in_thread(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(backup_mod, "seconds_until", lambda h, m: 0)
        monkeypatch.setattr(backup_mod, "run_backup",
                            lambda *a: calls.append(a) or SimpleNamespace(ok=True))
        task = asyncio.create_task(backup_mod.nightly_backup_loop(
            "x.db", BackupSettings(backup_dir=str(tmp_path))))
        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls and calls[0][2] == "notturno"


# ---------------------------------------------------------------
# SQLite tuning
# ---------------------------------------------------------------

class TestSqliteTuning:
    def test_pragmas_applied_to_new_engines(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
        with engine.connect() as c:
            assert c.exec_driver_sql("PRAGMA journal_size_limit").scalar() == \
                sqlite_tuning.JOURNAL_SIZE_LIMIT
            assert c.exec_driver_sql("PRAGMA synchronous").scalar() == 1  # NORMAL
            assert c.exec_driver_sql("PRAGMA temp_store").scalar() == 2  # MEMORY
        engine.dispose()

    def test_bbs_engine_tuned(self, db_session):
        assert db_session.execute(text("PRAGMA journal_size_limit")).scalar() == \
            sqlite_tuning.JOURNAL_SIZE_LIMIT
        assert db_session.execute(text("PRAGMA journal_mode")).scalar() == "wal"

    def test_checkpoint_truncates_wal(self, db_session, config):
        from bbs.models.user import User
        db_session.add(User(public_key="ab" * 6, nickname="x"))
        db_session.commit()
        result = sqlite_tuning.checkpoint()
        assert result is not None and result[0] == 0
        wal = Path(config.database_path + "-wal")
        assert not wal.exists() or wal.stat().st_size == 0

    def test_checkpoint_without_engine(self, monkeypatch):
        import bbs.models.base as base
        monkeypatch.setattr(base, "_engine", None)
        assert sqlite_tuning.checkpoint() is None

    @pytest.mark.asyncio
    async def test_periodic_checkpoint_survives_errors(self, monkeypatch):
        calls = []

        def boom():
            calls.append(1)
            raise RuntimeError("locked")
        monkeypatch.setattr(sqlite_tuning, "checkpoint", boom)
        task = asyncio.create_task(sqlite_tuning.periodic_checkpoint(interval=0.01))
        for _ in range(100):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(calls) >= 2


# ---------------------------------------------------------------
# Battery / node status
# ---------------------------------------------------------------

class TestBattery:
    @pytest.mark.parametrize("mv,pct", [
        (4250, 100), (4200, 100), (4100, 90), (4050, 85), (3800, 50),
        (3700, 30), (3575, 15), (3300, 0), (3000, 0),
    ])
    def test_lipo_curve(self, mv, pct):
        assert lipo_percent(mv) == pct

    @pytest.mark.parametrize("mv", [None, 0, -5, "abc"])
    def test_unknown(self, mv):
        assert lipo_percent(mv) is None

    def test_monotonic(self):
        values = [lipo_percent(mv) for mv in range(3300, 4201, 10)]
        assert values == sorted(values)


class TestNodeStatus:
    @pytest.mark.asyncio
    async def test_probe_captures_battery(self):
        from tests.test_radio_connection import make_connected
        conn, mc = make_connected()
        assert await conn.probe() is True
        assert conn.last_battery == {"level": 4100}

    @pytest.mark.asyncio
    async def test_query_device_info(self):
        from meshcore import EventType
        from meshcore.events import Event
        from tests.test_radio_connection import make_connected
        conn, mc = make_connected()
        mc.commands.send_device_query = AsyncMock(return_value=Event(
            EventType.DEVICE_INFO, {"model": "Heltec V3", "ver": "v1.9.1", "fw_build": "x"}))
        info = await conn.query_device_info()
        assert info["model"] == "Heltec V3" and info["firmware"] == "v1.9.1"
        assert conn.last_battery == {"level": 4100}

    @pytest.mark.asyncio
    async def test_query_device_info_errors_ignored(self):
        from tests.test_radio_connection import make_connected
        conn, mc = make_connected()
        mc.commands.send_device_query = AsyncMock(side_effect=OSError("x"))
        mc.commands.get_bat.side_effect = OSError("y")
        assert await conn.query_device_info() is None

    @pytest.mark.asyncio
    async def test_core_sync_updates_state(self, config):
        from bbs.core import BBSCore
        from meshbbs_radio.connection import MockMeshCoreConnection
        conn = MockMeshCoreConnection()
        conn.last_battery = {"level": 3950, "used_kb": 1, "total_kb": 2}
        conn.device_info = {"model": "RAK4631", "firmware": "v1.10"}
        core = BBSCore(config=config, connection=conn)
        core.state_manager = MeshCoreStateManager()
        await core.state_manager.set_connected("k" * 64, "n", "p")
        await core._sync_node_status(query=True)
        info = core.state_manager.state.radio_info
        assert info.battery_mv == 3950 and info.battery_level == 75
        assert info.model == "RAK4631" and info.firmware_version == "v1.10"


# ---------------------------------------------------------------
# Web (web_light): radio card + backup button
# ---------------------------------------------------------------

class TestWeb:
    @pytest.fixture(autouse=True)
    def _web(self, monkeypatch):
        import web_light.server as srv
        from tests import test_web_light_security as wsec
        monkeypatch.setattr(srv, "_admin_password", wsec.STRONG_PW)
        monkeypatch.setattr(srv, "_admin_username", "admin")
        srv._sessions.clear()
        srv._login_attempts.clear()
        self.srv, self.wsec = srv, wsec
        yield
        srv._sessions.clear()

    def test_format_battery(self):
        assert self.srv._format_battery(3950, 75) == "3.95 V (75%)"
        assert self.srv._format_battery(None, None) == "N/A"
        assert self.srv._format_battery(4100, None) == "4.10 V"

    def test_radio_card_shows_node_info_escaped(self, monkeypatch):
        srv, wsec = self.srv, self.wsec
        cookies, _ = wsec.auth()
        monkeypatch.setattr(srv, "_get_radio_status", lambda: {
            "connected": True, "status": "c", "messages_processed": 1, "name": "n",
            "port": "p", "battery_mv": 3950, "battery_level": 75,
            "node_key": "abcdef012345", "model": wsec.XSS, "firmware": "v1.9"})
        monkeypatch.setattr(srv, "_get_mesh_nodes", lambda refresh=False: [])
        monkeypatch.setattr(srv, "_get_stats", lambda: {})
        monkeypatch.setattr(srv, "_get_recent_activity", lambda limit=10: [])
        monkeypatch.setattr(srv, "_render_activity_chart", lambda: "")
        r = wsec.call("/api/partial/dashboard", cookies=cookies)
        assert "3.95 V (75%)" in r.body
        assert "abcdef012345" in r.body
        assert wsec.XSS not in r.body and "&lt;script&gt;" in r.body

    def test_backup_requires_csrf(self, config):
        cookies, _ = self.wsec.auth()
        r = self.wsec.call("/api/backup", method="POST", cookies=cookies,
                           headers={"Origin": self.wsec.ORIGIN})
        assert r.code == 403

    def test_backup_now_and_settings_card(self, config, db_session, tmp_path, monkeypatch):
        monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "bk"))
        monkeypatch.setattr(self.srv, "_get_radio_status",
                            lambda: {"connected": False, "status": "x", "messages_processed": 0})
        cookies, csrf = self.wsec.auth()
        r = self.wsec.call("/api/backup", method="POST", cookies=cookies,
                           headers={"Origin": self.wsec.ORIGIN, "X-CSRF-Token": csrf})
        data = r.json()
        assert data["ok"] is True, data
        assert len(list_backups(str(tmp_path / "bk"))) == 1
        r = self.wsec.call("/settings", cookies=cookies)
        assert "Backup database" in r.body and "Esegui backup ora" in r.body
        assert "nessuno" not in r.body
