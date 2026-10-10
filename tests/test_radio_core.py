"""
Tests for BBSCore radio handling: reconnect, keepalive, reply sending,
chunking, beacon, rate limiting, canonical user keys.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bbs.core import BBSCore, split_utf8_chunks, MAX_CHUNK_BYTES
from bbs.rate_limiter import RateLimiter
from meshbbs_radio.connection import MockMeshCoreConnection, TCPMeshCoreConnection
from meshbbs_radio.messages import Message


FULL_KEY = "ab" * 32


class ScriptedConnection(MockMeshCoreConnection):
    """Mock connection with scripted connect/probe/send results."""

    def __init__(self, connect_results=None, probe_results=None, send_results=None):
        super().__init__(node_name="TestBBS")
        self.connect_results = list(connect_results or [])
        self.probe_results = list(probe_results or [])
        self.send_results = list(send_results or [])
        self.connect_calls = 0
        self.probe_calls = 0
        self.adverts = []
        self.sent = []

    async def connect(self) -> bool:
        self.connect_calls += 1
        ok = self.connect_results.pop(0) if self.connect_results else True
        self.connected = ok
        return ok

    async def probe(self) -> bool:
        self.probe_calls += 1
        return self.probe_results.pop(0) if self.probe_results else True

    async def send_advert(self, flood: bool = False) -> bool:
        self.adverts.append(flood)
        return self.connected

    async def send_message(self, destination, text, use_path=True) -> bool:
        self.sent.append((destination, text))
        if self.send_results:
            return self.send_results.pop(0)
        return True


def fast(bbs: BBSCore) -> BBSCore:
    bbs.WATCHDOG_CHECK_INTERVAL = 0.01
    bbs.PROBE_INTERVAL = 0
    bbs.PROBE_RETRY_DELAY = 0
    bbs.RECONNECT_INITIAL_DELAY = 0.01
    bbs.RECONNECT_MAX_DELAY = 0.02
    return bbs


async def wait_until(predicate, timeout=2.0):
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if predicate():
            return True
        await asyncio.sleep(0.01)
    return predicate()


# ---------------------------------------------------------------------------
# Item 6: byte-based chunking
# ---------------------------------------------------------------------------

class TestChunking:

    def test_short_text_single_chunk(self):
        assert split_utf8_chunks("ciao\nmondo") == ["ciao\nmondo"]

    def test_chunks_respect_byte_budget(self):
        text = "\n".join(["è perché già così però " * 3] * 6)
        chunks = split_utf8_chunks(text)
        assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)
        assert "".join(chunks).replace("\n", "").replace(" ", "") == \
            text.replace("\n", "").replace(" ", "")

    def test_multibyte_never_cut(self):
        text = "🙂" * 100  # 4 bytes each, no spaces
        chunks = split_utf8_chunks(text)
        assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)
        assert "".join(chunks) == text
        for c in chunks:
            c.encode("utf-8").decode("utf-8")  # valid UTF-8

    def test_long_word_hard_split(self):
        word = "x" * 300
        chunks = split_utf8_chunks(f"inizio {word} fine")
        assert all(len(c.encode("utf-8")) <= MAX_CHUNK_BYTES for c in chunks)
        assert "".join(chunks).replace(" ", "") == f"inizio{word}fine"

    def test_ascii_line_packing_unchanged(self):
        lines = [f"riga {i:02d} " + "-" * 30 for i in range(10)]
        chunks = split_utf8_chunks("\n".join(lines))
        assert all(len(c) <= 140 for c in chunks)
        assert "\n".join(chunks) == "\n".join(lines)


# ---------------------------------------------------------------------------
# Item 7: reply sending
# ---------------------------------------------------------------------------

class TestSendResponse:

    @pytest.mark.asyncio
    async def test_stops_after_failed_chunk(self, config):
        config.send_delay = 0
        conn = ScriptedConnection(send_results=[True, False, True, True])
        bbs = BBSCore(config=config, connection=conn)
        text = "\n".join(["y" * 120] * 4)

        assert await bbs._send_response("a1b2c3d4e5f6", text) is False
        assert len(conn.sent) == 2

    @pytest.mark.asyncio
    async def test_all_chunks_sent(self, config):
        config.send_delay = 0
        conn = ScriptedConnection()
        bbs = BBSCore(config=config, connection=conn)
        assert await bbs._send_response("a1b2c3d4e5f6", "\n".join(["y" * 120] * 3)) is True
        assert len(conn.sent) == 3

    @pytest.mark.asyncio
    async def test_slow_reply_does_not_block_other_users(self, config):
        config.send_delay = 0
        release = asyncio.Event()
        sent = []

        class SlowConn(ScriptedConnection):
            async def send_message(self, destination, text, use_path=True):
                if destination == "slow00000000":
                    await release.wait()
                sent.append(destination)
                return True

        bbs = BBSCore(config=config, connection=SlowConn())
        bbs._queue_response("slow00000000", "risposta lunga")
        bbs._queue_response("fast00000000", "risposta breve")

        assert await wait_until(lambda: "fast00000000" in sent)
        assert "slow00000000" not in sent
        release.set()
        assert await wait_until(lambda: "slow00000000" in sent)
        assert await wait_until(lambda: not bbs._send_workers)
        assert bbs._send_queues == {}

    @pytest.mark.asyncio
    async def test_replies_to_same_user_stay_ordered(self, config):
        config.send_delay = 0
        conn = ScriptedConnection()
        bbs = BBSCore(config=config, connection=conn)
        for i in range(3):
            bbs._queue_response("a1b2c3d4e5f6", f"msg {i}")
        assert await wait_until(lambda: len(conn.sent) == 3)
        assert [t for _, t in conn.sent] == ["msg 0", "msg 1", "msg 2"]

    @pytest.mark.asyncio
    async def test_send_queue_bounded(self, config):
        config.send_delay = 0
        release = asyncio.Event()

        class Blocked(ScriptedConnection):
            async def send_message(self, destination, text, use_path=True):
                await release.wait()
                return True

        bbs = BBSCore(config=config, connection=Blocked())
        for i in range(30):
            bbs._queue_response("a1b2c3d4e5f6", f"msg {i}")
        await asyncio.sleep(0)
        assert bbs._send_queues["a1b2c3d4e5f6"].qsize() <= bbs.SEND_QUEUE_MAXSIZE
        release.set()
        await wait_until(lambda: not bbs._send_workers)


# ---------------------------------------------------------------------------
# Items 2 / 3: startup offline, reconnect, keepalive
# ---------------------------------------------------------------------------

class TestReconnect:

    def test_production_connection_has_no_mock_fallback(self, config):
        config.connection_mode = "tcp"
        bbs = BBSCore(config=config)
        assert isinstance(bbs.connection, TCPMeshCoreConnection)
        assert bbs.connection._use_mock_fallback is False

    def test_explicit_mock_flag(self, config):
        config.connection_mode = "tcp"
        bbs = BBSCore(config=config, use_mock_fallback=True)
        assert bbs.connection._use_mock_fallback is True

    @pytest.mark.asyncio
    async def test_start_with_radio_offline_keeps_retrying(self, config):
        conn = ScriptedConnection(connect_results=[False, False, False, True])
        bbs = fast(BBSCore(config=config, connection=conn))

        await bbs.start()  # must not raise
        try:
            assert bbs._running is True
            assert await wait_until(lambda: conn.connected and conn.connect_calls == 4)
            assert await wait_until(lambda: bbs.state_manager.is_connected)
            assert conn.adverts  # advert sent after reconnect
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_backoff_grows_and_caps(self, config):
        conn = ScriptedConnection(connect_results=[False] * 6 + [True])
        bbs = BBSCore(config=config, connection=conn)
        bbs.RECONNECT_INITIAL_DELAY = 5
        bbs._running = True
        delays = []

        async def fake_sleep(d):
            delays.append(d)

        with patch("bbs.core.asyncio.sleep", side_effect=fake_sleep):
            assert await bbs._do_reconnect(max_backoff=20) is True
        assert delays == [5, 10, 20, 20, 20, 20, 20]

    @pytest.mark.asyncio
    async def test_failed_probe_triggers_reconnect(self, config):
        conn = ScriptedConnection(probe_results=[False, False])
        bbs = fast(BBSCore(config=config, connection=conn))
        await bbs.start()
        try:
            assert await wait_until(lambda: conn.connect_calls >= 2)
            assert conn.probe_calls >= 2
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_single_probe_failure_is_retried(self, config):
        conn = ScriptedConnection(probe_results=[False, True])
        bbs = fast(BBSCore(config=config, connection=conn))
        bbs.PROBE_INTERVAL = 3600
        bbs._running = True
        assert await bbs._probe_link() is True
        assert conn.connect_calls == 0

    @pytest.mark.asyncio
    async def test_probe_runs_without_traffic(self, config):
        """Probe runs even though no message was ever received."""
        conn = ScriptedConnection()
        bbs = fast(BBSCore(config=config, connection=conn))
        await bbs.start()
        try:
            bbs._last_message_time = None
            calls = conn.probe_calls
            assert await wait_until(lambda: conn.probe_calls > calls)
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_link_lost_wakes_watchdog(self, config):
        conn = ScriptedConnection()
        bbs = BBSCore(config=config, connection=conn)
        bbs.WATCHDOG_CHECK_INTERVAL = 3600
        bbs.PROBE_INTERVAL = 3600
        bbs.RECONNECT_INITIAL_DELAY = 0.01
        await bbs.start()
        try:
            await asyncio.sleep(0.05)
            conn.connected = False
            bbs._on_link_lost("tcp_disconnect")
            assert await wait_until(lambda: conn.connect_calls >= 2)
        finally:
            await bbs.stop()

    def test_dashboard_shows_tcp_endpoint(self, config):
        config.connection_mode = "tcp"
        config.tcp_host = "10.1.2.3"
        config.tcp_port = 5000
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        assert bbs._connection_label() == "10.1.2.3:5000"

    @pytest.mark.asyncio
    async def test_dashboard_state_port_in_tcp_mode(self, config):
        config.connection_mode = "tcp"
        config.tcp_host = "10.1.2.3"
        config.tcp_port = 5000
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        await bbs.start()
        try:
            assert bbs.state_manager.state.radio_info.port == "10.1.2.3:5000"
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_housekeeping_flushes_pending_contacts(self, config):
        conn = ScriptedConnection()
        conn.flush_pending_contacts = MagicMock(return_value=3)
        bbs = BBSCore(config=config, connection=conn)
        bbs._housekeeping()
        conn.flush_pending_contacts.assert_called_once()


# ---------------------------------------------------------------------------
# Item 13: beacon
# ---------------------------------------------------------------------------

class TestBeacon:

    def test_broken_template_does_not_raise(self, config):
        config.beacon_message = "BBS {nome} attivo {"
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        assert bbs._beacon_text() == "BBS {nome} attivo {"

    def test_template_formatted(self, config):
        config.beacon_message = "{name} online"
        config.bbs_name = "0Bit"
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        assert bbs._beacon_text() == "0Bit online"

    @pytest.mark.asyncio
    async def test_beacon_survives_bad_template_and_failed_send(self, config):
        config.beacon_message = "{oops"
        config.beacon_interval = 1
        conn = ScriptedConnection()
        conn.connected = True
        conn.send_channel_message = AsyncMock(side_effect=[False, True])
        bbs = BBSCore(config=config, connection=conn)
        bbs._running = True

        sleeps = []

        async def fake_sleep(d):
            sleeps.append(d)
            if len(sleeps) > 2:
                bbs._running = False

        with patch("bbs.core.asyncio.sleep", side_effect=fake_sleep):
            await bbs._periodic_beacon()

        assert conn.send_channel_message.await_count == 2
        conn.send_channel_message.assert_awaited_with(0, "{oops")


# ---------------------------------------------------------------------------
# Items 5 / 14 / 15: dispatch, keys, rate limiter, logging
# ---------------------------------------------------------------------------

class FakeMC:
    def __init__(self, contacts):
        self.contacts = contacts
        self.commands = SimpleNamespace(get_contacts=AsyncMock())

    def get_contact_by_key_prefix(self, prefix):
        for c in self.contacts.values():
            if c["public_key"].startswith(prefix.lower()):
                return c
        return None

    def get_contact_by_name(self, name):
        for c in self.contacts.values():
            if c.get("adv_name", "").lower() == name.lower():
                return c
        return None


class TestDispatch:

    @pytest.mark.asyncio
    async def test_dm_and_channel_map_to_same_user(self, config):
        from bbs.models.base import get_session
        from bbs.models.user import User

        conn = ScriptedConnection()
        conn._meshcore = FakeMC({FULL_KEY: {"public_key": FULL_KEY, "adv_name": "Mario"}})
        bbs = BBSCore(config=config, connection=conn)
        await bbs.start()
        try:
            dm = Message(sender_key=FULL_KEY[:12], text="!help", recipient_key="x")
            assert await bbs.handle_message(dm)

            bbs.rate_limiter = RateLimiter(min_interval=0)
            chan = Message(sender_key="", text="!bbs", sender_name="Mario",
                           channel_idx=0, is_group_message=True)
            assert await bbs.handle_message(chan)
            assert chan.sender_key == FULL_KEY[:12]

            with get_session() as session:
                keys = [u.public_key for u in session.query(User).all()]
            assert keys.count(FULL_KEY[:12]) == 1
            assert FULL_KEY not in keys
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_channel_legacy_prefix_still_parsed(self, config):
        conn = ScriptedConnection()
        conn._meshcore = FakeMC({FULL_KEY: {"public_key": FULL_KEY, "adv_name": "Mario"}})
        bbs = BBSCore(config=config, connection=conn)
        await bbs.start()
        try:
            chan = Message(sender_key="", text="Mario: !bbs", channel_idx=0,
                           is_group_message=True)
            assert await bbs.handle_message(chan)
            ignored = Message(sender_key="", text="ciao a tutti",
                              sender_name="Mario", channel_idx=0, is_group_message=True)
            assert await bbs.handle_message(ignored) is None
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_rate_limiter_is_shared(self, config):
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        assert isinstance(bbs.rate_limiter, RateLimiter)
        await bbs.start()
        try:
            captured = []
            import bbs.core as core_mod
            real = core_mod.CommandDispatcher

            def spy(*args, **kwargs):
                captured.append(kwargs.get("rate_limiter"))
                return real(*args, **kwargs)

            with patch("bbs.core.CommandDispatcher", side_effect=spy):
                await bbs.handle_message(Message(sender_key="a1b2c3d4e5f6", text="!help"))
                await bbs.handle_message(Message(sender_key="a1b2c3d4e5f7", text="!help"))
            assert captured == [bbs.rate_limiter, bbs.rate_limiter]

            # Same user flooding is throttled by the long-lived limiter
            await bbs.handle_message(Message(sender_key="c0ffee000001", text="!help"))
            second = await bbs.handle_message(Message(sender_key="c0ffee000001", text="!help"))
            assert second and ("Troppo veloce" in second or "Troppi" in second)
        finally:
            await bbs.stop()

    @pytest.mark.asyncio
    async def test_message_text_not_logged_at_info(self, config, caplog):
        bbs = BBSCore(config=config, connection=ScriptedConnection())
        await bbs.start()
        try:
            secret = "testo-segretissimo"
            caplog.set_level(logging.INFO)
            for logger_name in ("meshbbs.core", "meshbbs"):
                logging.getLogger(logger_name).propagate = True
            with caplog.at_level(logging.INFO):
                await bbs.handle_message(Message(
                    sender_key="", text=f"Mario: {secret}", sender_name=None,
                    channel_idx=0, is_group_message=True,
                ))
            info = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
            assert any("Received channel" in m for m in info)
            assert not any(secret in m for m in info)
        finally:
            await bbs.stop()


# ---------------------------------------------------------------------------
# Launcher --mock
# ---------------------------------------------------------------------------

class TestLauncherMock:

    def test_mock_flag_default_off(self):
        from launcher import parse_args
        with patch("sys.argv", ["launcher.py"]):
            assert parse_args().mock is False
        with patch("sys.argv", ["launcher.py", "--mock"]):
            assert parse_args().mock is True

    @pytest.mark.asyncio
    async def test_run_all_passes_mock_flag(self, config):
        from launcher import parse_args, run_all
        with patch("sys.argv", ["launcher.py", "--bbs-only", "--mock"]):
            args = parse_args()
        calls = []

        async def fake_run_bbs(cfg, use_mock=False):
            calls.append(use_mock)

        with patch("launcher.run_bbs", side_effect=fake_run_bbs), \
             patch("launcher.logger", MagicMock()):
            await run_all(args, config)
        assert calls == [True]
