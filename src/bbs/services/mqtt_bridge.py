"""
MQTT bridge: BBS status/events to MQTT, Home Assistant discovery and a
couple of inbound commands.

MIT License - Copyright (c) 2026 MeshBBS Contributors

Enabled only with MQTT_ENABLED=true (see utils.mqtt.MQTTConfig).

Topics (<p> = MQTT_TOPIC_PREFIX, default "meshbbs"):
    <p>/availability        online/offline (retained, LWT)
    <p>/status              JSON every 60 s (retained)
    <p>/event/message       incoming radio message (metadata only)
    <p>/event/user_joined   new BBS user
    <p>/event/command       command executed (name only)
    <p>/event/cmd_result    outcome of an inbound command
    <p>/cmd/broadcast       payload text -> public channel (in)
    <p>/cmd/advert          send a flood advert (in)

Private message text is never published; channel text only with
MQTT_PUBLISH_CHANNEL_TEXT=true.
"""

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from utils.mqtt import MQTTClient, MQTTConfig

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.mqtt")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.mqtt")

VERSION = "1.6.0"

# Max broadcast payload (UTF-8 bytes), same limit as a radio chunk
MAX_BROADCAST_BYTES = 140

# Minimum seconds between two inbound commands (protects the airtime)
COMMAND_COOLDOWN = 10.0

# The bridge of the running BBS (module-level so the dispatcher can emit)
_active_bridge: Optional["MQTTBridge"] = None


def emit_event(kind: str, data: Dict[str, Any]) -> None:
    """Publish an event if the MQTT bridge is running (never raises)."""
    bridge = _active_bridge
    if bridge is None:
        return
    try:
        bridge.publish_event(kind, data)
    except Exception as e:
        logger.debug(f"MQTT event {kind} not published: {e}")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    """UTC ISO-8601 with offset (Home Assistant timestamp sensors need it)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat(timespec="seconds")


def _node_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text) or "meshbbs"


def build_discovery(config: MQTTConfig, bbs_name: str) -> List[tuple]:
    """
    Home Assistant MQTT discovery messages: [(topic, payload_dict), ...].

    All entities read <prefix>/status and share one device.
    """
    node = _node_id(config.topic_prefix)
    status_topic = config.topic("status")
    device = {
        "identifiers": [f"meshbbs_{node}"],
        "name": bbs_name or "MeshBBS",
        "manufacturer": "MeshBBS",
        "model": "MeshCore BBS",
        "sw_version": VERSION,
    }

    def entity(component: str, key: str, name: str, **extra) -> tuple:
        payload = {
            "name": name,
            "unique_id": f"meshbbs_{node}_{key}",
            "availability_topic": config.availability_topic,
            "device": device,
        }
        if component != "button":
            payload["state_topic"] = status_topic
        payload.update(extra)
        topic = f"{config.discovery_prefix}/{component}/{node}/{key}/config"
        return topic, payload

    msgs = [
        entity("sensor", "battery", "Batteria",
               value_template="{{ value_json.battery_percent }}",
               device_class="battery", unit_of_measurement="%",
               state_class="measurement"),
        entity("sensor", "battery_voltage", "Tensione batteria",
               value_template="{{ value_json.battery_mv }}",
               device_class="voltage", unit_of_measurement="mV",
               state_class="measurement", entity_category="diagnostic"),
        entity("binary_sensor", "radio", "Radio connessa",
               value_template="{{ 'ON' if value_json.radio_connected else 'OFF' }}",
               device_class="connectivity"),
        entity("sensor", "users", "Utenti",
               value_template="{{ value_json.users_total }}",
               state_class="measurement", icon="mdi:account-group"),
        entity("sensor", "messages_today", "Messaggi oggi",
               value_template="{{ value_json.messages_today }}",
               state_class="measurement", icon="mdi:message-text"),
        entity("sensor", "last_rssi", "Ultimo RSSI",
               value_template="{{ value_json.last_rssi }}",
               device_class="signal_strength", unit_of_measurement="dBm",
               state_class="measurement", entity_category="diagnostic"),
        entity("sensor", "last_snr", "Ultimo SNR",
               value_template="{{ value_json.last_snr }}",
               unit_of_measurement="dB", state_class="measurement",
               entity_category="diagnostic", icon="mdi:signal"),
        entity("sensor", "uptime", "Uptime",
               value_template="{{ value_json.uptime_s }}",
               device_class="duration", unit_of_measurement="s",
               entity_category="diagnostic"),
        entity("sensor", "last_message", "Ultimo messaggio",
               value_template="{{ value_json.last_message_at }}",
               device_class="timestamp"),
    ]
    if config.commands_enabled:
        msgs.append(entity("button", "advert", "Invia advert",
                           command_topic=config.topic("cmd/advert"),
                           payload_press="1", icon="mdi:access-point"))
    return msgs


def _db_counts() -> Dict[str, int]:
    """users_total / messages_today (board + PM) - blocking, run in a thread."""
    from bbs.models.base import get_session
    from bbs.models.message import Message
    from bbs.models.private_message import PrivateMessage
    from bbs.models.user import User

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with get_session() as session:
        users = session.query(User).count()
        board = session.query(Message).filter(Message.timestamp >= today).count()
        pms = session.query(PrivateMessage).filter(PrivateMessage.timestamp >= today).count()
    return {"users_total": users, "messages_today": board + pms}


class MQTTBridge:
    """Connects a running BBSCore to MQTT."""

    STATUS_INTERVAL = 60

    def __init__(self, bbs: Any, config: Optional[MQTTConfig] = None,
                 client: Optional[MQTTClient] = None):
        self.bbs = bbs
        self.config = config or MQTTConfig.from_env()
        self.client = client or MQTTClient(self.config)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._status_task: Optional[asyncio.Task] = None
        self._last_command = 0.0
        self.last_message_at: Optional[datetime] = None
        self.last_rssi: Optional[float] = None
        self.last_snr: Optional[float] = None

    # -- lifecycle -------------------------------------------------------

    async def start(self) -> bool:
        global _active_bridge
        self._loop = asyncio.get_running_loop()
        self.client.set_on_connect(self._on_connected)
        self.client.set_on_message(self._on_mqtt_message)
        if self.config.commands_enabled:
            self.client.subscribe(self.config.topic("cmd/#"))
        if self.config.discovery:
            # Republish discovery when Home Assistant restarts
            self.client.subscribe(f"{self.config.discovery_prefix}/status")
        if not self.client.start():
            return False
        _active_bridge = self
        self._status_task = asyncio.create_task(self._status_loop())
        return True

    async def stop(self) -> None:
        global _active_bridge
        if _active_bridge is self:
            _active_bridge = None
        if self._status_task is not None:
            self._status_task.cancel()
            try:
                await self._status_task
            except (asyncio.CancelledError, Exception):
                pass
            self._status_task = None
        await asyncio.to_thread(self.client.stop)

    # -- outbound ----------------------------------------------------------

    def publish_event(self, kind: str, data: Dict[str, Any]) -> bool:
        payload = dict(data)
        payload.setdefault("ts", _iso(datetime.utcnow()))
        return self.client.publish(self.config.topic(f"event/{kind}"), payload)

    def on_incoming_message(self, message: Any) -> None:
        """Record radio metrics and publish the event (metadata only)."""
        self.last_message_at = datetime.utcnow()
        if getattr(message, "rssi", None) is not None:
            self.last_rssi = message.rssi
        if getattr(message, "snr", None) is not None:
            self.last_snr = message.snr
        is_channel = bool(getattr(message, "is_channel", False))
        data = {
            "type": "channel" if is_channel else "private",
            "sender_name": getattr(message, "sender_name", None),
            "sender": (getattr(message, "sender_key", "") or "")[:8] or None,
            "hops": getattr(message, "hops", None),
            "rssi": message.rssi,
            "snr": message.snr,
            "length": len(getattr(message, "text", "") or ""),
        }
        if is_channel:
            data["channel"] = getattr(message, "channel_idx", 0)
            if self.config.publish_channel_text:
                data["text"] = message.text
        self.publish_event("message", data)

    def build_status(self, counts: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
        from bbs.runtime import get_uptime_seconds

        bbs = self.bbs
        sm = bbs.state_manager
        info = sm.state.radio_info
        connected = bool(sm.is_connected)
        identity = getattr(bbs.connection, "identity", None)
        pubkey = (getattr(identity, "public_key", "") or info.public_key or "")
        status = {
            "bbs_name": bbs.config.bbs_name,
            "version": VERSION,
            "radio_connected": connected,
            "radio_status": sm.status.value,
            "node_name": (getattr(identity, "name", None) or info.name or None),
            "node_key": pubkey[:12] or None,
            "model": info.model,
            "firmware": info.firmware_version,
            "battery_mv": info.battery_mv,
            "battery_percent": info.battery_level,
            "uptime_s": get_uptime_seconds(),
            "users_total": None,
            "messages_today": None,
            "last_message_at": _iso(self.last_message_at),
            "last_rssi": self.last_rssi,
            "last_snr": self.last_snr,
            "ts": _iso(datetime.utcnow()),
        }
        if counts:
            status.update(counts)
        return status

    async def publish_status(self) -> bool:
        if not self.client.is_connected:
            return False
        try:
            counts = await asyncio.to_thread(_db_counts)
        except Exception as e:
            logger.debug(f"MQTT status: DB counts failed: {e}")
            counts = None
        return self.client.publish(self.config.topic("status"), self.build_status(counts), retain=True)

    def publish_discovery(self) -> int:
        if not self.config.discovery:
            return 0
        sent = 0
        for topic, payload in build_discovery(self.config, self.bbs.config.bbs_name):
            if self.client.publish(topic, payload, retain=True, qos=1):
                sent += 1
        logger.debug(f"MQTT discovery: {sent} entita pubblicate")
        return sent

    async def _status_loop(self) -> None:
        while True:
            try:
                await self.publish_status()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"MQTT status publish failed: {e}")
            await asyncio.sleep(self.STATUS_INTERVAL)

    # -- paho thread -> asyncio ------------------------------------------

    def _on_connected(self) -> None:
        """Runs in the paho thread after each (re)connection."""
        self.publish_discovery()
        self._schedule(self.publish_status())

    def _schedule(self, coro) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            coro.close()
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, loop)
        except RuntimeError:
            coro.close()

    def _on_mqtt_message(self, topic: str, payload: bytes) -> None:
        """Runs in the paho thread: dispatch to the asyncio loop."""
        if topic == f"{self.config.discovery_prefix}/status":
            if payload.strip().lower() == b"online":
                logger.info("Home Assistant online: ripubblico discovery")
                self.publish_discovery()
            return
        prefix = self.config.topic("cmd/")
        if not topic.startswith(prefix):
            return
        command = topic[len(prefix):]
        if command not in ("broadcast", "advert"):
            logger.info(f"MQTT: comando ignorato '{command}'")
            return
        self._schedule(self.handle_command(command, payload))

    # -- inbound commands (asyncio loop) ----------------------------------

    async def handle_command(self, command: str, payload: bytes) -> bool:
        now = time.monotonic()
        if self._last_command and now - self._last_command < COMMAND_COOLDOWN:
            return self._command_result(command, False, "troppo frequente, riprova tra poco")

        bbs = self.bbs
        conn = bbs.connection
        if not getattr(bbs, "_running", False) or not getattr(conn, "connected", False):
            return self._command_result(command, False, "radio non connessa")

        if command == "broadcast":
            try:
                text = payload.decode("utf-8").strip()
            except UnicodeDecodeError:
                return self._command_result(command, False, "payload non UTF-8")
            if not text:
                return self._command_result(command, False, "messaggio vuoto")
            size = len(text.encode("utf-8"))
            if size > MAX_BROADCAST_BYTES:
                return self._command_result(
                    command, False, f"messaggio troppo lungo ({size}/{MAX_BROADCAST_BYTES} byte)")
            self._last_command = now
            sender = getattr(conn, "send_channel_message", None)
            ok = bool(sender and await sender(0, text))
            logger.info(f"MQTT broadcast sul canale ({size} byte): {'ok' if ok else 'fallito'}")
            return self._command_result(command, ok, None if ok else "invio fallito")

        if command == "advert":
            self._last_command = now
            ok = bool(await conn.send_advert(flood=True))
            logger.info(f"MQTT advert: {'ok' if ok else 'fallito'}")
            if ok:
                try:
                    from bbs.models.activity_log import EventType, log_activity
                    from bbs.models.base import get_session
                    with get_session() as session:
                        log_activity(session, EventType.ADVERT_SENT, details="MQTT")
                except Exception:
                    pass
            return self._command_result(command, ok, None if ok else "invio fallito")

        return False  # pragma: no cover - filtered in _on_mqtt_message

    def _command_result(self, command: str, ok: bool, error: Optional[str]) -> bool:
        if not ok:
            logger.warning(f"MQTT comando {command} rifiutato: {error}")
        self.publish_event("cmd_result", {"command": command, "ok": ok, "error": error})
        return ok


async def start_mqtt_bridge(bbs: Any) -> Optional[MQTTBridge]:
    """Start the bridge if MQTT_ENABLED=true (never raises)."""
    config = MQTTConfig.from_env()
    if not config.enabled:
        return None
    try:
        bridge = MQTTBridge(bbs, config)
        if await bridge.start():
            return bridge
    except Exception as e:
        logger.error(f"MQTT bridge not started: {e}")
    return None
