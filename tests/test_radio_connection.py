"""
Tests for the real-radio connection layer (meshcore 2.3.6), with a fake
MeshCore object: no radio required.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meshcore import EventType
from meshcore.events import Event, EventDispatcher
from meshcore.commands import CommandHandler

import meshbbs_radio.connection as connection_mod
from meshbbs_radio.connection import (
    MeshCoreConnection,
    TCPMeshCoreConnection,
    MockMeshCoreConnection,
    hops_from_payload,
    split_channel_sender,
)
from meshbbs_radio.messages import Message


FULL_KEY = "ab" * 32


def ok_event(event_type=EventType.OK, payload=None):
    return Event(event_type, payload if payload is not None else {})


class FakeCommands:
    """Stand-in for meshcore's CommandHandler."""

    def __init__(self):
        self.send = AsyncMock(return_value=ok_event())
        self.send_advert = AsyncMock(return_value=ok_event())
        self.send_appstart = AsyncMock(return_value=ok_event(EventType.SELF_INFO))
        self.set_flood_scope = AsyncMock(return_value=ok_event())
        self.get_contacts = AsyncMock(return_value=ok_event(EventType.CONTACTS, {}))
        self.send_msg_with_retry = AsyncMock(return_value=ok_event(EventType.MSG_SENT))
        self.send_chan_msg = AsyncMock(return_value=ok_event())
        self.get_bat = AsyncMock(return_value=ok_event(EventType.BATTERY, {"level": 4100}))


class FakeMeshCore:
    """Minimal MeshCore replacement used by connect() tests."""

    def __init__(self, connect_result="default", connect_exc=None, connect_delay=0.0,
                 start_fetch_exc=None):
        self.commands = FakeCommands()
        self.self_info = {"public_key": FULL_KEY, "name": "Radio BBS"}
        self.is_connected = True
        self.contacts = {}
        self.pending_contacts = {}
        self.subscriptions = []
        self.disconnected = False
        self.transport_closed = False
        self._connect_result = (
            ok_event(EventType.SELF_INFO, dict(self.self_info))
            if connect_result == "default" else connect_result
        )
        self._connect_exc = connect_exc
        self._connect_delay = connect_delay
        self._start_fetch_exc = start_fetch_exc
        cx = SimpleNamespace(disconnect=AsyncMock(side_effect=self._close_transport))
        self.connection_manager = SimpleNamespace(connection=cx)

    async def _close_transport(self):
        self.transport_closed = True

    async def connect(self):
        if self._connect_delay:
            await asyncio.sleep(self._connect_delay)
        if self._connect_exc:
            raise self._connect_exc
        return self._connect_result

    def subscribe(self, event_type, callback, attribute_filters=None):
        sub = SimpleNamespace(event_type=event_type, callback=callback)
        self.subscriptions.append(sub)
        return sub

    def unsubscribe(self, sub):
        if sub in self.subscriptions:
            self.subscriptions.remove(sub)

    async def disconnect(self):
        self.disconnected = True

    def stop(self):
        pass

    async def start_auto_message_fetching(self):
        if self._start_fetch_exc:
            raise self._start_fetch_exc

    async def stop_auto_message_fetching(self):
        pass

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

    def flush_pending_contacts(self):
        self.pending_contacts = {}

    def callback_for(self, event_type):
        for sub in self.subscriptions:
            if sub.event_type == event_type:
                return sub.callback
        return None


def make_connected(conn_cls=TCPMeshCoreConnection, **kwargs):
    """Return a connection wired to a FakeMeshCore as if connected."""
    conn = conn_cls(**kwargs)
    mc = FakeMeshCore()
    conn._meshcore = mc
    conn.connected = True
    conn._contacts_last_fetch = 0.0
    return conn, mc


@pytest.fixture
def patched_meshcore():
    """Patch MeshCore/TCPConnection constructors; yields a holder for the fake."""
    holder = {"mc": FakeMeshCore(), "built": []}

    def factory(*args, **kwargs):
        holder["built"].append(holder["mc"])
        return holder["mc"]

    with patch.object(connection_mod, "MeshCore", side_effect=factory), \
         patch.object(connection_mod, "TCPConnection", MagicMock()), \
         patch.object(connection_mod, "SerialConnection", MagicMock()):
        yield holder


# ---------------------------------------------------------------------------
# Item 1: advert
# ---------------------------------------------------------------------------

class TestSendAdvert:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("conn_cls", [TCPMeshCoreConnection, MeshCoreConnection])
    async def test_advert_uses_send_advert_and_keeps_scope(self, conn_cls):
        conn, mc = make_connected(conn_cls)

        assert await conn.send_advert(flood=True) is True

        mc.commands.send_advert.assert_awaited_once_with(flood=True)
        mc.commands.send_appstart.assert_not_called()
        mc.commands.set_flood_scope.assert_not_called()

    @pytest.mark.asyncio
    async def test_zero_hop_advert(self):
        conn, mc = make_connected()
        assert await conn.send_advert(flood=False) is True
        mc.commands.send_advert.assert_awaited_once_with(flood=False)

    @pytest.mark.asyncio
    async def test_advert_error_event_returns_false(self):
        conn, mc = make_connected()
        mc.commands.send_advert.return_value = Event(EventType.ERROR, {"reason": "timeout"})
        assert await conn.send_advert(flood=True) is False

    @pytest.mark.asyncio
    async def test_advert_not_connected(self):
        conn = TCPMeshCoreConnection()
        assert await conn.send_advert(flood=True) is False


# ---------------------------------------------------------------------------
# Item 2 + 10: connect, mock fallback, cleanup
# ---------------------------------------------------------------------------

class TestConnect:

    def test_mock_fallback_disabled_by_default(self):
        assert TCPMeshCoreConnection()._use_mock_fallback is False
        assert MeshCoreConnection()._use_mock_fallback is False

    @pytest.mark.asyncio
    async def test_connect_success(self, patched_meshcore):
        mc = patched_meshcore["mc"]
        conn = TCPMeshCoreConnection(host="10.0.0.2", port=5000)

        assert await conn.connect() is True
        assert conn.connected is True
        assert conn._meshcore is mc
        # self_info key in meshcore 2.3.6 is 'public_key'
        assert conn.identity.public_key == FULL_KEY
        assert conn.identity.name == "Radio BBS"
        # contacts loaded on connect
        mc.commands.get_contacts.assert_awaited()
        # handlers subscribed, including DISCONNECTED
        types = {s.event_type for s in mc.subscriptions}
        assert {EventType.CONTACT_MSG_RECV, EventType.CHANNEL_MSG_RECV,
                EventType.DISCONNECTED} <= types

    @pytest.mark.asyncio
    async def test_connect_failure_stays_disconnected_without_mock(self, patched_meshcore):
        patched_meshcore["mc"] = FakeMeshCore(connect_exc=ConnectionError("refused"))
        conn = TCPMeshCoreConnection()

        assert await conn.connect() is False
        assert conn.connected is False
        assert conn._mock is None
        assert conn.is_using_mock is False
        assert conn._meshcore is None

        # A later attempt retries the real radio
        patched_meshcore["mc"] = FakeMeshCore()
        assert await conn.connect() is True
        assert conn.is_using_mock is False
        assert len(patched_meshcore["built"]) == 2

    @pytest.mark.asyncio
    async def test_connect_failure_with_explicit_mock(self, patched_meshcore):
        patched_meshcore["mc"] = FakeMeshCore(connect_exc=ConnectionError("refused"))
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        assert await conn.connect() is True
        assert conn.is_using_mock is True

    @pytest.mark.asyncio
    async def test_no_appstart_response_cleans_up(self, patched_meshcore):
        mc = FakeMeshCore(connect_result=None)
        patched_meshcore["mc"] = mc
        conn = TCPMeshCoreConnection()

        assert await conn.connect() is False
        assert mc.disconnected is True
        assert conn._meshcore is None

    @pytest.mark.asyncio
    async def test_partial_connect_failure_disconnects(self, patched_meshcore):
        mc = FakeMeshCore(start_fetch_exc=RuntimeError("boom"))
        patched_meshcore["mc"] = mc
        conn = TCPMeshCoreConnection()

        assert await conn.connect() is False
        assert mc.disconnected is True
        assert conn.connected is False
        assert conn._meshcore is None
        assert mc.subscriptions == []

    @pytest.mark.asyncio
    async def test_connect_timeout(self, patched_meshcore):
        mc = FakeMeshCore(connect_delay=5)
        patched_meshcore["mc"] = mc
        conn = TCPMeshCoreConnection()
        conn.CONNECT_TIMEOUT = 0.05

        assert await conn.connect() is False
        assert mc.disconnected is True
        # transport closed explicitly when the handshake never completed
        mc.is_connected = False
        mc2 = FakeMeshCore(connect_delay=5)
        mc2.is_connected = False
        patched_meshcore["mc"] = mc2
        assert await conn.connect() is False
        assert mc2.transport_closed is True

    @pytest.mark.asyncio
    async def test_disconnected_event_notifies(self, patched_meshcore):
        mc = patched_meshcore["mc"]
        conn = TCPMeshCoreConnection()
        reasons = []
        conn.set_link_lost_callback(reasons.append)
        await conn.connect()

        handler = mc.callback_for(EventType.DISCONNECTED)
        await handler(Event(EventType.DISCONNECTED, {"reason": "tcp_disconnect"}))

        assert reasons == ["tcp_disconnect"]
        assert conn.connected is False

    @pytest.mark.asyncio
    async def test_disconnect_releases_meshcore(self, patched_meshcore):
        mc = patched_meshcore["mc"]
        conn = TCPMeshCoreConnection()
        await conn.connect()
        await conn.disconnect()

        assert mc.disconnected is True
        assert conn._meshcore is None
        assert conn.connected is False


# ---------------------------------------------------------------------------
# Item 3 / 16: probe, flush
# ---------------------------------------------------------------------------

class TestProbe:

    @pytest.mark.asyncio
    async def test_probe_ok(self):
        conn, mc = make_connected()
        assert await conn.probe() is True
        mc.commands.get_bat.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_probe_error_event_is_failure(self):
        conn, mc = make_connected()
        mc.commands.get_bat.return_value = Event(EventType.ERROR, {"reason": "no_event_received"})
        assert await conn.probe() is False

    @pytest.mark.asyncio
    async def test_probe_exception_is_failure(self):
        conn, mc = make_connected()
        mc.commands.get_bat.side_effect = OSError("broken pipe")
        assert await conn.probe() is False

    @pytest.mark.asyncio
    async def test_probe_transport_down(self):
        conn, mc = make_connected()
        mc.is_connected = False
        assert await conn.probe() is False
        mc.commands.get_bat.assert_not_called()

    def test_flush_pending_contacts(self):
        conn, mc = make_connected()
        mc.pending_contacts = {"a": {}, "b": {}}
        assert conn.flush_pending_contacts() == 2
        assert mc.pending_contacts == {}


# ---------------------------------------------------------------------------
# Item 4: payload keys, channel sender name
# ---------------------------------------------------------------------------

class TestPayloadParsing:

    def test_hops_from_path_len(self):
        assert hops_from_payload({"path_len": 3}) == 3
        assert hops_from_payload({"path_len": 0}) == 0
        assert hops_from_payload({"path_len": 255}) == 0  # direct route
        assert hops_from_payload({"hops": 2}) == 2       # legacy key
        assert hops_from_payload({}) == 0

    def test_split_channel_sender(self):
        assert split_channel_sender("Mario: !bbs") == ("Mario", "!bbs")
        assert split_channel_sender("Mario Rossi: ciao: a tutti") == ("Mario Rossi", "ciao: a tutti")
        assert split_channel_sender("senza prefisso") == (None, "senza prefisso")

    @pytest.mark.asyncio
    async def test_private_message_keys(self):
        conn, _ = make_connected()
        conn.identity = connection_mod.Identity(public_key=FULL_KEY, name="BBS")
        await conn._on_private_message(Event(EventType.CONTACT_MSG_RECV, {
            "type": "PRIV", "pubkey_prefix": "a1b2c3d4e5f6", "path_len": 2,
            "SNR": 6.25, "text": "!help",
        }))
        msg = conn._message_queue.get_nowait()
        assert msg.sender_key == "a1b2c3d4e5f6"
        assert msg.hops == 2
        assert msg.snr == 6.25
        assert msg.text == "!help"

    @pytest.mark.asyncio
    async def test_channel_message_sender_name(self):
        conn, _ = make_connected()
        await conn._on_channel_message(Event(EventType.CHANNEL_MSG_RECV, {
            "type": "CHAN", "channel_idx": 0, "path_len": 1,
            "SNR": -3.5, "RSSI": -101, "text": "Mario: !bbs",
        }))
        msg = conn._message_queue.get_nowait()
        assert msg.sender_key == ""
        assert msg.sender_name == "Mario"
        assert msg.sender_short == "Mario"
        assert msg.text == "!bbs"
        assert msg.rssi == -101
        assert msg.snr == -3.5
        assert msg.hops == 1
        assert msg.is_channel


# ---------------------------------------------------------------------------
# Item 7: bounded incoming queue
# ---------------------------------------------------------------------------

class TestBoundedQueue:

    def test_queue_drops_oldest(self):
        conn = TCPMeshCoreConnection()
        assert conn._message_queue.maxsize == 100
        for i in range(105):
            conn._enqueue_message(Message(sender_key=f"{i:012x}", text=str(i)))
        assert conn._message_queue.qsize() == 100
        first = conn._message_queue.get_nowait()
        assert first.text == "5"

    def test_mock_queue_bounded(self):
        assert MockMeshCoreConnection()._message_queue.maxsize == 100


# ---------------------------------------------------------------------------
# Item 8: command serialisation
# ---------------------------------------------------------------------------

class TestCommandLock:

    async def _run_two_commands(self, lock: bool):
        dispatcher = EventDispatcher()
        await dispatcher.start()
        commands = CommandHandler()
        commands.set_dispatcher(dispatcher)

        async def device(data: bytes):
            # The device answers each command with a MSG_SENT tagged with it
            async def reply():
                await asyncio.sleep(0.02)
                await dispatcher.dispatch(Event(EventType.MSG_SENT, {"for": data}))
            asyncio.create_task(reply())

        commands._sender_func = device
        if lock:
            conn = TCPMeshCoreConnection()
            conn._install_command_lock(SimpleNamespace(commands=commands))

        r1, r2 = await asyncio.gather(
            commands.send(b"A", [EventType.MSG_SENT, EventType.ERROR], timeout=2),
            commands.send(b"B", [EventType.MSG_SENT, EventType.ERROR], timeout=2),
        )
        await dispatcher.stop()
        return r1, r2

    @pytest.mark.asyncio
    async def test_without_lock_responses_are_stolen(self):
        r1, r2 = await self._run_two_commands(lock=False)
        # Documents the meshcore race the lock fixes
        assert r1.payload["for"] == r2.payload["for"]

    @pytest.mark.asyncio
    async def test_lock_keeps_responses_paired(self):
        r1, r2 = await self._run_two_commands(lock=True)
        assert r1.payload["for"] == b"A"
        assert r2.payload["for"] == b"B"

    @pytest.mark.asyncio
    async def test_fire_and_forget_not_locked(self):
        conn = TCPMeshCoreConnection()
        commands = SimpleNamespace(send=AsyncMock(return_value=ok_event()))
        conn._install_command_lock(SimpleNamespace(commands=commands))
        async with conn._command_lock:
            # would deadlock if fire-and-forget sends took the lock
            await asyncio.wait_for(commands.send(b"\x04"), timeout=1)


# ---------------------------------------------------------------------------
# Item 11: TCP send path refreshes stale contacts
# ---------------------------------------------------------------------------

class TestSendMessage:

    @pytest.mark.asyncio
    async def test_tcp_send_refreshes_stale_contacts(self):
        conn, mc = make_connected()
        mc.contacts = {FULL_KEY: {"public_key": FULL_KEY, "adv_name": "Mario"}}

        assert await conn.send_message(FULL_KEY[:12], "ciao") is True

        mc.commands.get_contacts.assert_awaited_once()
        target = mc.commands.send_msg_with_retry.call_args[0][0]
        assert target["public_key"] == FULL_KEY

        # Fresh cache: no second fetch
        assert await conn.send_message(FULL_KEY[:12], "ancora") is True
        assert mc.commands.get_contacts.await_count == 1

    @pytest.mark.asyncio
    async def test_send_failure_returns_false(self):
        conn, mc = make_connected()
        mc.commands.send_msg_with_retry.return_value = None
        assert await conn.send_message(FULL_KEY, "ciao") is False

    @pytest.mark.asyncio
    async def test_channel_message_error(self):
        conn, mc = make_connected()
        assert await conn.send_channel_message(0, "beacon") is True
        mc.commands.send_chan_msg.return_value = Event(EventType.ERROR, {})
        assert await conn.send_channel_message(0, "beacon") is False
