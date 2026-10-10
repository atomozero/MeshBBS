"""
Tests for the node history: debounced sightings, retention, !nodes,
advert events from meshcore, web network page (escaping, 7-day chart).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import bbs.models.base as db_base
from bbs.commands.base import CommandContext
from bbs.commands.nodes_cmd import NodesCommand
from bbs.core import BBSCore
from bbs.models.node_sighting import NodeSighting, NodeSightingDay
from bbs.services.node_history import (
    NodeHistory, format_ago, local_day, node_prefix, nodes_per_day,
)
from meshbbs_radio.connection import MockMeshCoreConnection, TCPMeshCoreConnection
from meshbbs_radio.messages import Message

KEY = "abcdef012345" + "00" * 26
PFX = "abcdef012345"


class Clock:
    def __init__(self, start=None):
        self.now = start or datetime.utcnow()

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += timedelta(**kw)


def row(prefix=PFX):
    with db_base.get_session() as s:
        r = s.get(NodeSighting, prefix)
        if r is None:
            return None
        s.expunge(r)
        return r


class TestRecording:

    def test_prefix(self):
        assert node_prefix(KEY.upper()) == PFX
        assert node_prefix(bytes.fromhex(KEY)) == PFX
        assert node_prefix("xyz") is None and node_prefix(None) is None

    def test_first_sighting_written(self, db_session):
        h = NodeHistory(clock=Clock())
        assert h.record(KEY, name="Rpt", node_type=2, hops=1, lat=45.1, lon=12.2) is True
        r = row()
        assert (r.name, r.node_type, r.last_hops, r.count) == ("Rpt", 2, 1, 1)
        assert (r.lat, r.lon) == (45.1, 12.2)

    def test_debounce_one_write_per_five_minutes(self, db_session):
        clock = Clock()
        h = NodeHistory(clock=clock)
        h.record(KEY, name="A")
        for _ in range(10):
            clock.advance(seconds=20)
            assert h.record(KEY, snr=5.5) is False
        assert row().count == 1  # nothing written meanwhile
        clock.advance(minutes=2)
        assert h.record(KEY, rssi=-90) is True
        r = row()
        assert r.count == 12 and r.snr == 5.5 and r.rssi == -90
        assert r.name == "A"  # not wiped by sightings without a name

    def test_flush_all_writes_accumulated(self, db_session):
        clock = Clock()
        h = NodeHistory(clock=clock)
        h.record(KEY)
        clock.advance(seconds=30)
        h.record(KEY)
        assert h.flush_all() == 1
        assert row().count == 2

    def test_bad_values_ignored(self, db_session):
        h = NodeHistory(clock=Clock())
        h.record(KEY, name="\x00\x07Nodo\n", hops="x", snr=float("nan"), lat=0.0, lon=0.0)
        r = row()
        assert r.name == "Nodo" and r.last_hops is None and r.snr is None and r.lat is None

    def test_retention_30_days(self, db_session):
        clock = Clock()
        h = NodeHistory(clock=clock)
        h.record(KEY)
        h.record("111111111111")
        clock.advance(days=31)
        h.record("111111111111")
        assert h.purge() == 1
        assert row() is None and row("111111111111") is not None
        with db_base.get_session() as s:
            days = {d.day for d in s.query(NodeSightingDay).all()}
        assert days == {local_day(clock.now)}

    def test_nodes_per_day(self, db_session):
        clock = Clock(datetime.utcnow() - timedelta(days=3))
        h = NodeHistory(clock=clock)
        h.record("111111111111")
        h.record("222222222222")
        clock.advance(days=2)
        h.record("111111111111")
        with db_base.get_session() as s:
            data = nodes_per_day(s, days=7, today=local_day(datetime.utcnow()))
        assert len(data) == 7
        counts = [c for _, c in data]
        assert counts[3] == 2 and counts[5] == 1 and sum(counts) == 3

    def test_format_ago(self):
        now = datetime.utcnow()
        assert format_ago(now - timedelta(seconds=5), now) == "5s"
        assert format_ago(now - timedelta(minutes=7), now) == "7m"
        assert format_ago(now - timedelta(hours=3), now) == "3h"
        assert format_ago(now - timedelta(days=2), now) == "2g"
        assert format_ago(None) == "?"


class TestCoreHooks:

    async def test_message_and_advert_recorded(self, config, db_session):
        conn = MockMeshCoreConnection()
        core = BBSCore(config=config, connection=conn)
        core.rate_limiter = None
        await core.handle_message(Message(sender_key=PFX, text="!ping", hops=2, snr=7.25, rssi=-80))
        r = row()
        assert (r.last_hops, r.snr, r.rssi, r.count) == (2, 7.25, -80, 1)

        core.node_history.WRITE_INTERVAL = timedelta(0)
        core._on_advert({"public_key": KEY, "name": "Mario", "type": 1, "path_len": 3,
                         "lat": 45.0, "lon": 12.0})
        r = row()
        assert (r.name, r.node_type, r.last_hops, r.count) == ("Mario", 1, 3, 2)

    async def test_retention_hooked(self, config, db_session):
        core = BBSCore(config=config, connection=MockMeshCoreConnection())
        called = []
        core.node_history.purge = lambda: called.append(1) or 0
        core._running = True
        import bbs.core as core_mod
        real_sleep = core_mod.asyncio.sleep

        async def fake_sleep(sec):
            if sec >= 86400:
                core._running = False
            return await real_sleep(0)

        core_mod.asyncio.sleep = fake_sleep
        try:
            await core._periodic_retention_cleanup()
        finally:
            core_mod.asyncio.sleep = real_sleep
        assert called == [1]


class TestAdvertEvents:

    async def test_advertisement_uses_contact_details(self):
        conn = TCPMeshCoreConnection(host="127.0.0.1", port=1)
        got = []
        conn.set_advert_callback(got.append)
        conn._meshcore = SimpleNamespace(
            contacts={KEY: {"public_key": KEY, "adv_name": "Rpt1", "type": 2,
                            "out_path_len": 2, "adv_lat": 45.5, "adv_lon": 12.5}},
            pending_contacts={},
        )
        await conn._on_advert_event(SimpleNamespace(payload={"public_key": KEY}))
        assert got == [{"public_key": KEY, "name": "Rpt1", "type": 2, "path_len": 2,
                        "lat": 45.5, "lon": 12.5}]

    async def test_new_contact_payload_and_flood_path(self):
        conn = TCPMeshCoreConnection(host="127.0.0.1", port=1)
        got = []
        conn.set_advert_callback(got.append)
        payload = {"public_key": KEY, "adv_name": "Nuovo", "type": 1, "out_path_len": -1,
                   "adv_lat": 0.0, "adv_lon": 0.0}
        await conn._on_advert_event(SimpleNamespace(payload=payload))
        assert got[0]["name"] == "Nuovo" and got[0]["path_len"] is None

    async def test_callback_errors_contained(self):
        conn = TCPMeshCoreConnection(host="127.0.0.1", port=1)

        def boom(info):
            raise RuntimeError("x")

        conn.set_advert_callback(boom)
        await conn._on_advert_event(SimpleNamespace(payload={"public_key": KEY}))
        await conn._on_advert_event(SimpleNamespace(payload=None))


class TestNodesCommand:

    def ctx(self):
        return CommandContext(sender_key="a1a1a1a1a1a1", sender_name="adm",
                              raw_message="!nodes", is_admin=True)

    async def test_history_sorted_and_bounded(self, db_session):
        clock = Clock(datetime.utcnow() - timedelta(hours=1))
        h = NodeHistory(clock=clock)
        for i in range(20):
            clock.advance(minutes=1)
            h.record(f"{i:012x}", name=f"nodo{i}", node_type=2 if i % 2 else 1, hops=i % 3)
        result = await NodesCommand(db_session).execute(self.ctx(), [])
        lines = result.response.split("\n")
        assert lines[0].startswith("[BBS] Nodi sentiti: 20")
        assert len(lines) == 1 + NodesCommand.DEFAULT_LIMIT
        assert lines[1].startswith("[R]nodo19 1h ")  # most recent first
        result = await NodesCommand(db_session).execute(self.ctx(), ["99"])
        assert len(result.response.split("\n")) == 1 + NodesCommand.MAX_LIMIT
        result = await NodesCommand(db_session).execute(self.ctx(), ["x"])
        assert not result.success

    async def test_empty_history_falls_back(self, db_session):
        result = await NodesCommand(db_session).execute(self.ctx(), [])
        # No BBS running in tests: fallback reports the service as inactive
        assert "[BBS]" in result.response


class TestWebNetwork:

    def test_history_section_escapes_names(self, db_session):
        import web_light.server as srv
        xss = "<script>alert(1)</script>"
        h = NodeHistory(clock=Clock())
        h.record(KEY, name=xss + "\"'", node_type=2, hops=1, snr=3.0, rssi=-70)
        html = srv._render_node_history()
        assert xss not in html and "&lt;script&gt;" in html
        assert "<svg" in html and "Nodi sentiti per giorno" in html
        assert "<rect" in html and PFX in html

    def test_network_page_includes_history(self, db_session, monkeypatch):
        from tests.test_web_light_security import auth, call
        import web_light.server as srv
        h = NodeHistory(clock=Clock())
        h.record(KEY, name="<b>evil</b>", node_type=1)
        monkeypatch.setattr(srv, "_admin_password", "S3cure-Test-Passw0rd!")
        monkeypatch.setattr(srv, "_get_mesh_nodes", lambda refresh=False: [])
        monkeypatch.setattr(srv, "_render_repeater_telemetry", lambda: "")
        cookies, _ = auth()
        r = call("/network", cookies=cookies)
        assert r.code == 200
        assert "Storico nodi" in r.body
        assert "<b>evil</b>" not in r.body and "&lt;b&gt;evil&lt;/b&gt;" in r.body

    def test_svg_chart_values(self):
        import web_light.server as srv
        today = datetime.utcnow().date()
        per_day = [(today - timedelta(days=6 - i), i) for i in range(7)]
        svg = srv._render_nodes_per_day_svg(per_day)
        assert svg.count("<rect") == 7
        assert ">6</text>" in svg

    def test_history_unavailable_is_silent(self, monkeypatch):
        import web_light.server as srv

        def boom():
            raise RuntimeError("db down")

        monkeypatch.setattr(srv, "_get_node_history", boom)
        assert srv._render_node_history() == ""
