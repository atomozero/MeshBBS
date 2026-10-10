"""
Tests for the repeater telemetry monitor (meshcore *_sync helpers).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from meshcore import EventType
from meshcore.events import Event

from meshbbs_radio.repeater_monitor import RepeaterMonitor, RepeaterTarget


RPT_KEY = "cd" * 32


def make_monitor(tmp_path, contacts=None, login=None, status=None, connected=True):
    contacts = {RPT_KEY: {"public_key": RPT_KEY, "adv_name": "Rpt"}} if contacts is None else contacts

    def by_prefix(prefix):
        for c in contacts.values():
            if c["public_key"].startswith(prefix):
                return c
        return None

    commands = SimpleNamespace(
        send_login_sync=AsyncMock(return_value=login),
        req_status_sync=AsyncMock(return_value=status),
        send_logout=AsyncMock(),
        send_login=AsyncMock(),
        send_statusreq=AsyncMock(),
    )
    mc = SimpleNamespace(commands=commands, get_contact_by_key_prefix=by_prefix)
    connection = SimpleNamespace(
        _meshcore=mc, connected=connected,
        refresh_contacts=AsyncMock(return_value=True),
    )
    bbs = SimpleNamespace(connection=connection)
    target = RepeaterTarget(name="Rpt", public_key=RPT_KEY, password_env="RPT_PWD")
    monitor = RepeaterMonitor(
        bbs=bbs, targets=[target], jsonl_path=str(tmp_path / "rpt.jsonl"),
    )
    return monitor, target, mc, connection


class TestRepeaterPoll:

    @pytest.mark.asyncio
    async def test_successful_poll_uses_sync_helpers(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setenv("RPT_PWD", "segreta")
        status = {"pubkey_pre": RPT_KEY[:12], "bat": 4012, "uptime": 3600}
        monitor, target, mc, _ = make_monitor(
            tmp_path, login=Event(EventType.LOGIN_SUCCESS, {}), status=status,
        )

        await monitor._poll_target(target)

        mc.commands.send_login_sync.assert_awaited_once()
        mc.commands.req_status_sync.assert_awaited_once()
        mc.commands.send_login.assert_not_called()
        mc.commands.send_statusreq.assert_not_called()
        mc.commands.send_logout.assert_awaited_once()
        assert target.last_error is None
        assert target.last_sample["bat"] == 4012
        line = json.loads((tmp_path / "rpt.jsonl").read_text().strip())
        assert line["uptime"] == 3600

    @pytest.mark.asyncio
    async def test_log_uses_bat_and_uptime_keys(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "segreta")
        status = {"bat": 3900, "uptime": 120}
        monitor, target, _, _ = make_monitor(
            tmp_path, login=Event(EventType.LOGIN_SUCCESS, {}), status=status,
        )
        import meshbbs_radio.repeater_monitor as rm
        rm_logger = MagicMock()
        monkeypatch.setattr(rm, "logger", rm_logger)

        await monitor._poll_target(target)

        msg = rm_logger.info.call_args[0][0]
        assert "batt=3900mV" in msg
        assert "uptime=120s" in msg

    @pytest.mark.asyncio
    async def test_login_failure(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "sbagliata")
        monitor, target, mc, _ = make_monitor(tmp_path, login=None)

        await monitor._poll_target(target)

        assert "login failed" in target.last_error
        mc.commands.req_status_sync.assert_not_called()
        mc.commands.send_logout.assert_not_called()

    @pytest.mark.asyncio
    async def test_status_timeout(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "segreta")
        monitor, target, mc, _ = make_monitor(
            tmp_path, login=Event(EventType.LOGIN_SUCCESS, {}), status=None,
        )
        await monitor._poll_target(target)
        assert target.last_error == "status response timeout"
        mc.commands.send_logout.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_connected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "segreta")
        monitor, target, mc, _ = make_monitor(tmp_path, connected=False)
        await monitor._poll_target(target)
        assert target.last_error == "radio not connected"
        mc.commands.send_login_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_contacts_refreshed_before_cycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "segreta")
        monitor, target, _, connection = make_monitor(tmp_path)
        await monitor._refresh_contacts()
        connection.refresh_contacts.assert_awaited_once_with(force=True)

    @pytest.mark.asyncio
    async def test_missing_contact(self, tmp_path, monkeypatch):
        monkeypatch.setenv("RPT_PWD", "segreta")
        monitor, target, mc, _ = make_monitor(tmp_path, contacts={})
        await monitor._poll_target(target)
        assert target.last_error == "contact not in companion contact list"
        mc.commands.send_login_sync.assert_not_called()
