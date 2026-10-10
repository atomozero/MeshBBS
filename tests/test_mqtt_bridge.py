"""
Tests for the MQTT client wrapper and the BBS MQTT bridge (paho mocked:
no broker needed).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bbs.services.mqtt_bridge as bridge_mod
from bbs.services.mqtt_bridge import (
    MAX_BROADCAST_BYTES,
    MQTTBridge,
    build_discovery,
    emit_event,
    start_mqtt_bridge,
)
from meshbbs_radio.messages import Message
from meshbbs_radio.state import MeshCoreStateManager
from utils.mqtt import MQTTClient, MQTTConfig


class FakePaho:
    """Records what the wrapper does with the paho client."""

    def __init__(self):
        self.published = []
        self.subscribed = []
        self.will = None
        self.auth = None
        self.connected_to = None
        self.loop_started = False
        self.loop_stopped = False
        self.disconnected = False
        self.on_connect = self.on_disconnect = self.on_message = None

    def username_pw_set(self, user, password):
        self.auth = (user, password)

    def will_set(self, topic, payload=None, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay=1, max_delay=120):
        self.delays = (min_delay, max_delay)

    def connect_async(self, host, port, keepalive=60):
        self.connected_to = (host, port)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_stopped = True

    def disconnect(self):
        self.disconnected = True

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, qos, retain))
        return SimpleNamespace(rc=0, wait_for_publish=lambda timeout=None: True)

    # helpers
    def topics(self):
        return [p[0] for p in self.published]

    def last(self, topic):
        for t, payload, qos, retain in reversed(self.published):
            if t == topic:
                return payload, retain
        return None


SUCCESS = SimpleNamespace(is_failure=False)
REFUSED = SimpleNamespace(is_failure=True)


def make_client(**cfg):
    config = MQTTConfig(enabled=True, **cfg)
    fake = FakePaho()
    client = MQTTClient(config, client_factory=lambda: fake)
    return client, fake


def connect(client, fake):
    """Simulate the paho thread reporting a successful connection."""
    fake.on_connect(fake, None, {}, SUCCESS, None)


# ---------------------------------------------------------------
# Config
# ---------------------------------------------------------------

class TestConfig:
    def test_defaults(self, monkeypatch):
        for k in ("MQTT_ENABLED", "MQTT_HOST", "MQTT_PORT", "MQTT_TOPIC_PREFIX",
                  "MQTT_DISCOVERY", "MQTT_DISCOVERY_PREFIX", "MQTT_CLIENT_ID",
                  "MQTT_USERNAME", "MQTT_PASSWORD", "MQTT_PUBLISH_CHANNEL_TEXT"):
            monkeypatch.delenv(k, raising=False)
        c = MQTTConfig.from_env()
        assert c.enabled is False
        assert (c.host, c.port) == ("localhost", 1883)
        assert c.topic_prefix == "meshbbs"
        assert c.discovery is True and c.discovery_prefix == "homeassistant"
        assert c.username is None and c.password is None
        assert c.publish_channel_text is False
        assert c.availability_topic == "meshbbs/availability"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("MQTT_ENABLED", "true")
        monkeypatch.setenv("MQTT_HOST", "broker")
        monkeypatch.setenv("MQTT_PORT", "1884")
        monkeypatch.setenv("MQTT_USERNAME", "u")
        monkeypatch.setenv("MQTT_PASSWORD", "p")
        monkeypatch.setenv("MQTT_TOPIC_PREFIX", "/0bit/")
        monkeypatch.setenv("MQTT_DISCOVERY", "false")
        monkeypatch.setenv("MQTT_CLIENT_ID", "pi-bbs")
        c = MQTTConfig.from_env()
        assert c.enabled and c.host == "broker" and c.port == 1884
        assert (c.username, c.password) == ("u", "p")
        assert c.topic_prefix == "0bit"
        assert c.discovery is False
        assert c.client_id == "pi-bbs"

    def test_bad_port_falls_back(self, monkeypatch):
        monkeypatch.setenv("MQTT_PORT", "abc")
        assert MQTTConfig.from_env().port == 1883


# ---------------------------------------------------------------
# MQTTClient wrapper
# ---------------------------------------------------------------

class TestClient:
    def test_start_sets_lwt_auth_and_loop(self):
        client, fake = make_client(username="u", password="p")
        assert client.start() is True
        assert fake.will == ("meshbbs/availability", "offline", 1, True)
        assert fake.auth == ("u", "p")
        assert fake.connected_to == ("localhost", 1883)
        assert fake.loop_started is True

    def test_no_auth_when_no_username(self):
        client, fake = make_client()
        client.start()
        assert fake.auth is None

    def test_publish_requires_connection(self):
        client, fake = make_client()
        client.start()
        assert client.publish("t", {"a": 1}) is False
        connect(client, fake)
        assert client.publish("t", {"a": 1}) is True
        assert fake.last("t") == ('{"a":1}', False)

    def test_on_connect_publishes_online_and_resubscribes(self):
        client, fake = make_client()
        client.subscribe("meshbbs/cmd/#")
        called = []
        client.set_on_connect(lambda: called.append(True))
        client.start()
        connect(client, fake)
        assert fake.last("meshbbs/availability") == ("online", True)
        assert "meshbbs/cmd/#" in fake.subscribed
        assert called == [True]
        # Reconnect: subscriptions restored again
        fake.on_disconnect(fake, None, {}, SimpleNamespace(is_failure=True), None)
        assert client.is_connected is False
        connect(client, fake)
        assert fake.subscribed.count("meshbbs/cmd/#") == 2

    def test_refused_connection(self):
        client, fake = make_client()
        client.start()
        fake.on_connect(fake, None, {}, REFUSED, None)
        assert client.is_connected is False
        assert "meshbbs/availability" not in fake.topics()

    def test_v1_style_callbacks_accepted(self):
        client, fake = make_client()
        client.start()
        fake.on_connect(fake, None, {}, 0)  # paho 1.x: rc int, no properties
        assert client.is_connected
        fake.on_disconnect(fake, None, 1)
        assert not client.is_connected

    def test_stop_publishes_offline(self):
        client, fake = make_client()
        client.start()
        connect(client, fake)
        client.stop()
        assert fake.last("meshbbs/availability") == ("offline", True)
        assert fake.disconnected and fake.loop_stopped
        client.stop()  # idempotent

    def test_message_callback_errors_contained(self):
        client, fake = make_client()

        def boom(topic, payload):
            raise ValueError("x")
        client.set_on_message(boom)
        client.start()
        fake.on_message(fake, None, SimpleNamespace(topic="a", payload=b"b"))  # no raise

    def test_setup_error_never_raises(self):
        def factory():
            raise OSError("no socket")
        client = MQTTClient(MQTTConfig(enabled=True), client_factory=factory)
        assert client.start() is False

    def test_real_paho_v2_client_builds(self):
        paho = pytest.importorskip("paho.mqtt.client")
        client = MQTTClient(MQTTConfig(enabled=True, client_id="t"))
        built = client._build_client()
        assert isinstance(built, paho.Client)
        if hasattr(paho, "CallbackAPIVersion"):
            assert built._callback_api_version == paho.CallbackAPIVersion.VERSION2


# ---------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------

def make_bbs(connected=True):
    sm = MeshCoreStateManager()
    conn = SimpleNamespace(
        connected=connected,
        identity=SimpleNamespace(public_key="abcdef0123456789" * 4, name="0Bit BBS"),
        send_channel_message=AsyncMock(return_value=True),
        send_advert=AsyncMock(return_value=True),
    )
    bbs = SimpleNamespace(
        state_manager=sm,
        connection=conn,
        config=SimpleNamespace(bbs_name="0Bit BBS", database_path="x.db"),
        _running=True,
    )
    return bbs


def make_bridge(bbs=None, **cfg):
    config = MQTTConfig(enabled=True, **cfg)
    fake = FakePaho()
    client = MQTTClient(config, client_factory=lambda: fake)
    bridge = MQTTBridge(bbs or make_bbs(), config, client)
    return bridge, client, fake


@pytest.fixture(autouse=True)
def _no_active_bridge():
    yield
    bridge_mod._active_bridge = None


class TestDiscovery:
    def test_entities_and_device(self):
        config = MQTTConfig(enabled=True)
        msgs = dict(build_discovery(config, "0Bit BBS"))
        expected = {
            "homeassistant/sensor/meshbbs/battery/config",
            "homeassistant/sensor/meshbbs/battery_voltage/config",
            "homeassistant/binary_sensor/meshbbs/radio/config",
            "homeassistant/sensor/meshbbs/users/config",
            "homeassistant/sensor/meshbbs/messages_today/config",
            "homeassistant/sensor/meshbbs/last_rssi/config",
            "homeassistant/sensor/meshbbs/last_snr/config",
            "homeassistant/sensor/meshbbs/uptime/config",
            "homeassistant/sensor/meshbbs/last_message/config",
            "homeassistant/button/meshbbs/advert/config",
        }
        assert set(msgs) == expected
        ids = {p["unique_id"] for p in msgs.values()}
        assert len(ids) == len(msgs)
        for payload in msgs.values():
            assert payload["device"]["name"] == "0Bit BBS"
            assert payload["device"]["identifiers"] == ["meshbbs_meshbbs"]
            assert payload["availability_topic"] == "meshbbs/availability"
        bat = msgs["homeassistant/sensor/meshbbs/battery/config"]
        assert bat["state_topic"] == "meshbbs/status"
        assert bat["device_class"] == "battery" and bat["unit_of_measurement"] == "%"
        assert "battery_percent" in bat["value_template"]
        radio = msgs["homeassistant/binary_sensor/meshbbs/radio/config"]
        assert radio["device_class"] == "connectivity"
        button = msgs["homeassistant/button/meshbbs/advert/config"]
        assert button["command_topic"] == "meshbbs/cmd/advert"
        assert "state_topic" not in button

    def test_custom_prefixes_and_no_button_without_commands(self):
        config = MQTTConfig(enabled=True, topic_prefix="0bit", discovery_prefix="ha",
                            commands_enabled=False)
        msgs = dict(build_discovery(config, "X"))
        assert all(t.startswith("ha/") for t in msgs)
        assert not any("/button/" in t for t in msgs)
        assert all(p["state_topic"] == "0bit/status" for p in msgs.values())

    @pytest.mark.asyncio
    async def test_published_retained_on_connect(self):
        bridge, client, fake = make_bridge()
        bridge._loop = asyncio.get_running_loop()
        client.start()
        bridge.client.set_on_connect(bridge._on_connected)
        connect(client, fake)
        disc = [p for p in fake.published if p[0].startswith("homeassistant/")]
        assert len(disc) == 10
        assert all(p[3] is True for p in disc)  # retained
        json.loads(disc[0][1])

    def test_discovery_disabled(self):
        bridge, client, fake = make_bridge(discovery=False)
        client.start()
        connect(client, fake)
        assert bridge.publish_discovery() == 0

    def test_ha_birth_message_republishes(self):
        bridge, client, fake = make_bridge()
        client.start()
        connect(client, fake)
        fake.published.clear()
        bridge._on_mqtt_message("homeassistant/status", b"online")
        assert any(t.startswith("homeassistant/") for t in fake.topics())


class TestStatus:
    @pytest.mark.asyncio
    async def test_status_json(self):
        bbs = make_bbs()
        await bbs.state_manager.set_connected("abcdef0123456789" * 4, "0Bit BBS", "tcp")
        await bbs.state_manager.update_battery(3900)
        await bbs.state_manager.update_device_info("T-Beam", "v1.9")
        bridge, client, fake = make_bridge(bbs)
        bridge.on_incoming_message(Message(sender_key="aa" * 6, text="x", rssi=-90, snr=7.5))
        status = bridge.build_status({"users_total": 4, "messages_today": 9})
        assert status["radio_connected"] is True
        assert status["node_name"] == "0Bit BBS"
        assert status["node_key"] == "abcdef012345"
        assert status["battery_mv"] == 3900 and status["battery_percent"] == 70
        assert status["model"] == "T-Beam" and status["firmware"] == "v1.9"
        assert status["users_total"] == 4 and status["messages_today"] == 9
        assert status["last_rssi"] == -90 and status["last_snr"] == 7.5
        assert status["last_message_at"].endswith("+00:00")
        assert isinstance(status["uptime_s"], int)
        json.dumps(status)

    @pytest.mark.asyncio
    async def test_publish_status_retained(self, db_session):
        bridge, client, fake = make_bridge()
        client.start()
        connect(client, fake)
        assert await bridge.publish_status() is True
        payload, retain = fake.last("meshbbs/status")
        assert retain is True
        data = json.loads(payload)
        assert data["users_total"] == 0 and data["messages_today"] == 0
        assert data["radio_connected"] is False

    @pytest.mark.asyncio
    async def test_publish_status_skipped_when_offline(self):
        bridge, client, fake = make_bridge()
        client.start()
        assert await bridge.publish_status() is False
        assert fake.published == []


class TestEvents:
    def _started(self, **cfg):
        bridge, client, fake = make_bridge(**cfg)
        client.start()
        connect(client, fake)
        return bridge, fake

    def test_private_message_never_includes_text(self):
        bridge, fake = self._started(publish_channel_text=True)
        bridge.on_incoming_message(Message(sender_key="abcdef123456", text="segreto",
                                           hops=2, rssi=-100, snr=-3.0))
        data = json.loads(fake.last("meshbbs/event/message")[0])
        assert "text" not in data
        assert "segreto" not in fake.last("meshbbs/event/message")[0]
        assert data["type"] == "private" and data["sender"] == "abcdef12"
        assert data["hops"] == 2 and data["length"] == 7 and data["snr"] == -3.0

    def test_channel_text_only_when_enabled(self):
        msg = Message(sender_key="", text="ciao", sender_name="Bob",
                      is_group_message=True, channel_idx=0)
        bridge, fake = self._started()
        bridge.on_incoming_message(msg)
        data = json.loads(fake.last("meshbbs/event/message")[0])
        assert data["type"] == "channel" and data["sender_name"] == "Bob"
        assert "text" not in data
        bridge, fake = self._started(publish_channel_text=True)
        bridge.on_incoming_message(msg)
        assert json.loads(fake.last("meshbbs/event/message")[0])["text"] == "ciao"

    @pytest.mark.asyncio
    async def test_emit_event_via_active_bridge(self):
        bridge, client, fake = make_bridge()
        await bridge.start()
        connect(client, fake)
        emit_event("command", {"command": "help", "ok": True})
        data = json.loads(fake.last("meshbbs/event/command")[0])
        assert data["command"] == "help" and "ts" in data
        await bridge.stop()
        emit_event("command", {"command": "x"})  # no bridge: no-op

    @pytest.mark.asyncio
    async def test_dispatcher_emits_user_joined_and_command(self, db_session):
        from bbs.commands.dispatcher import CommandDispatcher
        bridge, client, fake = make_bridge()
        await bridge.start()
        connect(client, fake)
        try:
            d = CommandDispatcher(session=db_session)
            await d.dispatch("!help", sender_key="ab12cd34ef56")
        finally:
            await bridge.stop()
        joined = json.loads(fake.last("meshbbs/event/user_joined")[0])
        assert joined["user"] == "ab12cd34"
        cmd = json.loads(fake.last("meshbbs/event/command")[0])
        assert cmd == {"command": "help", "ok": True, "ts": cmd["ts"]}


class TestInboundCommands:
    @pytest.mark.asyncio
    async def test_broadcast(self):
        bridge, client, fake = make_bridge()
        client.start()
        connect(client, fake)
        assert await bridge.handle_command("broadcast", "Ciao à tutti".encode()) is True
        bridge.bbs.connection.send_channel_message.assert_awaited_once_with(0, "Ciao à tutti")
        assert json.loads(fake.last("meshbbs/event/cmd_result")[0])["ok"] is True

    @pytest.mark.asyncio
    async def test_broadcast_too_long_or_empty(self):
        bridge, client, fake = make_bridge()
        assert await bridge.handle_command("broadcast", b"x" * (MAX_BROADCAST_BYTES + 1)) is False
        assert await bridge.handle_command("broadcast", b"   ") is False
        assert await bridge.handle_command("broadcast", b"\xff\xfe") is False
        bridge.bbs.connection.send_channel_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_advert_and_cooldown(self, db_session):
        bridge, client, fake = make_bridge()
        assert await bridge.handle_command("advert", b"") is True
        bridge.bbs.connection.send_advert.assert_awaited_once_with(flood=True)
        # second command within the cooldown is refused
        assert await bridge.handle_command("broadcast", b"hi") is False
        bridge.bbs.connection.send_channel_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_radio_down(self):
        bridge, client, fake = make_bridge(make_bbs(connected=False))
        assert await bridge.handle_command("advert", b"") is False
        bridge.bbs.connection.send_advert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_dispatch_from_paho_thread(self):
        bridge, client, fake = make_bridge()
        bridge.handle_command = AsyncMock(return_value=True)
        bridge._loop = asyncio.get_running_loop()
        t = threading.Thread(target=bridge._on_mqtt_message,
                             args=("meshbbs/cmd/broadcast", b"hello"))
        t.start()
        t.join()
        for _ in range(50):
            if bridge.handle_command.await_count:
                break
            await asyncio.sleep(0.01)
        bridge.handle_command.assert_awaited_once_with("broadcast", b"hello")

    @pytest.mark.asyncio
    async def test_unknown_commands_ignored(self):
        bridge, client, fake = make_bridge()
        bridge.handle_command = AsyncMock()
        bridge._loop = asyncio.get_running_loop()
        bridge._on_mqtt_message("meshbbs/cmd/reboot", b"")
        bridge._on_mqtt_message("other/topic", b"")
        await asyncio.sleep(0.02)
        bridge.handle_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_commands_disabled_no_subscription(self):
        bridge, client, fake = make_bridge(commands_enabled=False)
        await bridge.start()
        connect(client, fake)
        assert "meshbbs/cmd/#" not in fake.subscribed
        await bridge.stop()


class TestStartup:
    @pytest.mark.asyncio
    async def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("MQTT_ENABLED", raising=False)
        assert await start_mqtt_bridge(make_bbs()) is None

    @pytest.mark.asyncio
    async def test_broker_down_never_fatal(self, monkeypatch):
        monkeypatch.setenv("MQTT_ENABLED", "true")
        failing = MagicMock(side_effect=OSError("refused"))
        monkeypatch.setattr(bridge_mod.MQTTClient, "_build_client", failing)
        assert await start_mqtt_bridge(make_bbs()) is None
