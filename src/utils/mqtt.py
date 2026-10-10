"""
Thin MQTT client wrapper for MeshBBS (paho-mqtt, callback API v2).

MIT License - Copyright (c) 2026 MeshBBS Contributors

The network loop runs in paho's own thread (loop_start), so nothing here
ever blocks the asyncio loop. paho reconnects automatically (with
backoff) after a lost connection and keeps retrying the first connection
too, so a broker that is down at boot is never fatal.

BBS specific logic (status, events, Home Assistant discovery, inbound
commands) lives in bbs.services.mqtt_bridge.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.mqtt")
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger("meshbbs.mqtt")

# paho-mqtt is optional
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the install
    mqtt = None
    MQTT_AVAILABLE = False


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        logger.warning(f"Invalid {name}, using {default}")
        return default


@dataclass
class MQTTConfig:
    """MQTT settings (from the environment / config.env)."""

    enabled: bool = False
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "meshbbs"
    topic_prefix: str = "meshbbs"
    discovery: bool = True
    discovery_prefix: str = "homeassistant"
    publish_channel_text: bool = False
    commands_enabled: bool = True
    keepalive: int = 60

    @classmethod
    def from_env(cls) -> "MQTTConfig":
        prefix = (os.getenv("MQTT_TOPIC_PREFIX") or "meshbbs").strip().strip("/") or "meshbbs"
        return cls(
            enabled=_env_bool("MQTT_ENABLED", False),
            host=(os.getenv("MQTT_HOST") or "localhost").strip(),
            port=_env_int("MQTT_PORT", 1883),
            username=os.getenv("MQTT_USERNAME") or None,
            password=os.getenv("MQTT_PASSWORD") or None,
            client_id=(os.getenv("MQTT_CLIENT_ID") or f"meshbbs-{prefix}").strip(),
            topic_prefix=prefix,
            discovery=_env_bool("MQTT_DISCOVERY", True),
            discovery_prefix=(os.getenv("MQTT_DISCOVERY_PREFIX") or "homeassistant").strip().strip("/"),
            publish_channel_text=_env_bool("MQTT_PUBLISH_CHANNEL_TEXT", False),
            commands_enabled=_env_bool("MQTT_COMMANDS_ENABLED", True),
        )

    def topic(self, suffix: str) -> str:
        return f"{self.topic_prefix}/{suffix}"

    @property
    def availability_topic(self) -> str:
        return self.topic("availability")


def _reason_failed(reason_code: Any) -> bool:
    """True if a connect reason code (v2 ReasonCode or v1 int) is a failure."""
    is_failure = getattr(reason_code, "is_failure", None)
    if is_failure is not None:
        return bool(is_failure)
    try:
        return int(reason_code) != 0
    except (TypeError, ValueError):
        return True


class MQTTClient:
    """
    paho wrapper: LWT on the availability topic, auto-reconnect,
    thread-safe publish, subscriptions restored on every (re)connect.

    Callbacks registered with set_on_connect / set_on_message run in the
    paho network thread: they must not touch asyncio objects directly.
    """

    def __init__(self, config: MQTTConfig, client_factory: Optional[Callable[..., Any]] = None):
        self.config = config
        self._client_factory = client_factory
        self._client: Any = None
        self._connected = False
        self._subscriptions: List[str] = []
        self._on_connect_cb: Optional[Callable[[], None]] = None
        self._on_message_cb: Optional[Callable[[str, bytes], None]] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    def set_on_connect(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_connect_cb = callback

    def set_on_message(self, callback: Optional[Callable[[str, bytes], None]]) -> None:
        self._on_message_cb = callback

    def subscribe(self, topic: str) -> None:
        """Subscribe now (if connected) and again after every reconnect."""
        if topic not in self._subscriptions:
            self._subscriptions.append(topic)
        if self._connected and self._client is not None:
            try:
                self._client.subscribe(topic, qos=0)
            except Exception as e:
                logger.warning(f"MQTT subscribe {topic} failed: {e}")

    def _build_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        if hasattr(mqtt, "CallbackAPIVersion"):
            return mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self.config.client_id,
                protocol=mqtt.MQTTv311,
            )
        # paho-mqtt 1.x (the callbacks below accept both signatures)
        return mqtt.Client(client_id=self.config.client_id, protocol=mqtt.MQTTv311)  # pragma: no cover

    def start(self) -> bool:
        """
        Start the background network loop (never blocks, never raises).

        Returns:
            False if MQTT cannot be used (paho missing or setup error)
        """
        if self._client_factory is None and not MQTT_AVAILABLE:
            logger.warning("MQTT_ENABLED but paho-mqtt is not installed (pip install paho-mqtt)")
            return False
        try:
            client = self._build_client()
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            if self.config.username:
                client.username_pw_set(self.config.username, self.config.password)
            client.will_set(self.config.availability_topic, payload="offline", qos=1, retain=True)
            client.reconnect_delay_set(min_delay=2, max_delay=120)
            client.connect_async(self.config.host, self.config.port, keepalive=self.config.keepalive)
            client.loop_start()
            self._client = client
            logger.info(f"MQTT: connessione a {self.config.host}:{self.config.port} in background")
            return True
        except Exception as e:
            logger.error(f"MQTT setup failed: {e}")
            self._client = None
            return False

    def stop(self) -> None:
        """Publish 'offline', disconnect and stop the loop (blocking, short)."""
        client = self._client
        if client is None:
            return
        self._client = None
        try:
            if self._connected:
                info = client.publish(self.config.availability_topic, "offline", qos=1, retain=True)
                try:
                    info.wait_for_publish(timeout=2)
                except Exception:
                    pass
            client.disconnect()
        except Exception as e:
            logger.debug(f"MQTT disconnect error: {e}")
        try:
            client.loop_stop()
        except Exception:
            pass
        self._connected = False
        logger.info("MQTT disconnesso")

    def publish(self, topic: str, payload: Any, retain: bool = False, qos: int = 0) -> bool:
        """Publish (thread-safe, non-blocking). dict/list payloads become JSON."""
        client = self._client
        if client is None or not self._connected:
            return False
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            info = client.publish(topic, payload, qos=qos, retain=retain)
            rc = getattr(info, "rc", 0)
            return rc == 0
        except Exception as e:
            logger.debug(f"MQTT publish {topic} failed: {e}")
            return False

    # -- paho callbacks (network thread) -------------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if _reason_failed(reason_code):
            self._connected = False
            logger.warning(f"MQTT connessione rifiutata: {reason_code}")
            return
        self._connected = True
        logger.info(f"MQTT connesso a {self.config.host}:{self.config.port}")
        try:
            client.publish(self.config.availability_topic, "online", qos=1, retain=True)
            for topic in self._subscriptions:
                client.subscribe(topic, qos=0)
        except Exception as e:
            logger.warning(f"MQTT post-connect error: {e}")
        if self._on_connect_cb is not None:
            try:
                self._on_connect_cb()
            except Exception as e:
                logger.error(f"MQTT on_connect callback error: {e}")

    def _on_disconnect(self, client, userdata, *args):
        # v2: (flags, reason_code, properties) - v1: (rc,)
        was_connected = self._connected
        self._connected = False
        if was_connected and self._client is not None:
            reason = args[1] if len(args) >= 2 else (args[0] if args else "?")
            logger.warning(f"MQTT disconnesso ({reason}), riconnessione automatica")

    def _on_message(self, client, userdata, msg):
        if self._on_message_cb is None:
            return
        try:
            self._on_message_cb(msg.topic, msg.payload or b"")
        except Exception as e:
            logger.error(f"MQTT message handler error: {e}")
