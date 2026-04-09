"""
MQTT integration for MeshBBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors

This module provides MQTT client integration for publishing BBS events
to an MQTT broker, enabling integration with home automation systems,
monitoring dashboards, and other IoT applications.
"""

import asyncio
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Callable, Awaitable, Any, Dict, List

try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.mqtt")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.mqtt")

# Try to import paho-mqtt (optional dependency)
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None


@dataclass
class MQTTConfig:
    """MQTT client configuration."""

    enabled: bool = False
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "meshbbs"
    topic_prefix: str = "meshbbs"
    tls_enabled: bool = False
    tls_ca_certs: Optional[str] = None
    tls_certfile: Optional[str] = None
    tls_keyfile: Optional[str] = None
    keepalive: int = 60
    qos: int = 1
    retain: bool = False

    @classmethod
    def from_env(cls) -> 'MQTTConfig':
        """Create config from environment variables."""
        return cls(
            enabled=os.getenv('MQTT_ENABLED', 'false').lower() == 'true',
            host=os.getenv('MQTT_HOST', 'localhost'),
            port=int(os.getenv('MQTT_PORT', '1883')),
            username=os.getenv('MQTT_USERNAME'),
            password=os.getenv('MQTT_PASSWORD'),
            client_id=os.getenv('MQTT_CLIENT_ID', 'meshbbs'),
            topic_prefix=os.getenv('MQTT_TOPIC_PREFIX', 'meshbbs'),
            tls_enabled=os.getenv('MQTT_TLS_ENABLED', 'false').lower() == 'true',
            tls_ca_certs=os.getenv('MQTT_TLS_CA_CERTS'),
            tls_certfile=os.getenv('MQTT_TLS_CERTFILE'),
            tls_keyfile=os.getenv('MQTT_TLS_KEYFILE'),
            keepalive=int(os.getenv('MQTT_KEEPALIVE', '60')),
            qos=int(os.getenv('MQTT_QOS', '1')),
            retain=os.getenv('MQTT_RETAIN', 'false').lower() == 'true',
        )


class MQTTClient:
    """
    MQTT client for publishing BBS events.

    Publishes events like:
    - meshbbs/status - BBS online/offline status
    - meshbbs/message - New messages
    - meshbbs/user - User events (login, logout, registration)
    - meshbbs/system - System events (backup, errors)
    """

    def __init__(self, config: Optional[MQTTConfig] = None):
        """
        Initialize MQTT client.

        Args:
            config: MQTT configuration. If None, loads from environment.
        """
        self.config = config or MQTTConfig.from_env()
        self._client: Optional[Any] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None
        self._message_callbacks: List[Callable] = []

        if not MQTT_AVAILABLE:
            if self.config.enabled:
                logger.warning(
                    "MQTT is enabled but paho-mqtt is not installed. "
                    "Install with: pip install paho-mqtt"
                )
            self.config.enabled = False

    async def connect(self) -> bool:
        """
        Connect to the MQTT broker.

        Returns:
            True if connection successful
        """
        if not self.config.enabled:
            logger.debug("MQTT is disabled, skipping connection")
            return False

        if not MQTT_AVAILABLE:
            return False

        try:
            # Create client
            self._client = mqtt.Client(
                client_id=self.config.client_id,
                protocol=mqtt.MQTTv311,
            )

            # Set callbacks
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message

            # Set authentication if provided
            if self.config.username:
                self._client.username_pw_set(
                    self.config.username,
                    self.config.password
                )

            # Set TLS if enabled
            if self.config.tls_enabled:
                self._client.tls_set(
                    ca_certs=self.config.tls_ca_certs,
                    certfile=self.config.tls_certfile,
                    keyfile=self.config.tls_keyfile,
                )

            # Set last will (offline status)
            self._client.will_set(
                f"{self.config.topic_prefix}/status",
                payload=json.dumps({
                    "status": "offline",
                    "timestamp": datetime.utcnow().isoformat(),
                }),
                qos=self.config.qos,
                retain=True,
            )

            # Connect
            logger.info(f"Connecting to MQTT broker at {self.config.host}:{self.config.port}")
            self._client.connect_async(
                self.config.host,
                self.config.port,
                keepalive=self.config.keepalive,
            )

            # Start network loop
            self._client.loop_start()

            # Wait for connection
            for _ in range(50):  # 5 seconds timeout
                if self._connected:
                    return True
                await asyncio.sleep(0.1)

            logger.warning("MQTT connection timeout")
            return False

        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client:
            try:
                # Publish offline status
                await self.publish_status("offline")

                # Stop reconnect task
                if self._reconnect_task:
                    self._reconnect_task.cancel()
                    try:
                        await self._reconnect_task
                    except asyncio.CancelledError:
                        pass

                # Disconnect
                self._client.loop_stop()
                self._client.disconnect()
                logger.info("MQTT disconnected")

            except Exception as e:
                logger.error(f"MQTT disconnect error: {e}")

            finally:
                self._client = None
                self._connected = False

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            logger.info("MQTT connected successfully")
            self._connected = True

            # Publish online status
            self._publish_sync(
                f"{self.config.topic_prefix}/status",
                {
                    "status": "online",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                retain=True,
            )

            # Subscribe to command topics
            self._client.subscribe(f"{self.config.topic_prefix}/command/#")

        else:
            logger.error(f"MQTT connection failed with code: {rc}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        logger.warning(f"MQTT disconnected (rc={rc})")
        self._connected = False

    def _on_message(self, client, userdata, msg):
        """Callback when message received."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            logger.debug(f"MQTT message received: {topic}")

            # Notify callbacks
            for callback in self._message_callbacks:
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error(f"MQTT callback error: {e}")

        except Exception as e:
            logger.error(f"MQTT message processing error: {e}")

    def on_message(self, callback: Callable[[str, dict], None]) -> None:
        """Register a callback for incoming MQTT messages."""
        self._message_callbacks.append(callback)

    async def publish(
        self,
        topic: str,
        payload: dict,
        retain: Optional[bool] = None,
    ) -> bool:
        """
        Publish a message to an MQTT topic.

        Args:
            topic: Topic name (will be prefixed automatically)
            payload: Message payload (will be JSON encoded)
            retain: Whether to retain the message

        Returns:
            True if publish successful
        """
        if not self._connected or not self._client:
            return False

        full_topic = f"{self.config.topic_prefix}/{topic}"
        return self._publish_sync(full_topic, payload, retain)

    def _publish_sync(
        self,
        topic: str,
        payload: dict,
        retain: Optional[bool] = None,
    ) -> bool:
        """Synchronous publish helper."""
        try:
            message = json.dumps(payload)
            result = self._client.publish(
                topic,
                message,
                qos=self.config.qos,
                retain=retain if retain is not None else self.config.retain,
            )
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")
            return False

    async def publish_status(self, status: str, details: Optional[dict] = None) -> bool:
        """
        Publish BBS status update.

        Args:
            status: Status string (online, offline, maintenance, etc.)
            details: Optional additional details
        """
        payload = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if details:
            payload.update(details)

        return await self.publish("status", payload, retain=True)

    async def publish_message(
        self,
        sender_key: str,
        sender_name: Optional[str],
        text: str,
        area: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> bool:
        """
        Publish a new message event.

        Args:
            sender_key: Sender's public key
            sender_name: Sender's display name
            text: Message text
            area: Message area (None for private messages)
            message_id: Optional message ID
        """
        return await self.publish("message", {
            "sender_key": sender_key,
            "sender_name": sender_name,
            "text": text,
            "area": area,
            "message_id": message_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def publish_user_event(
        self,
        event_type: str,
        user_key: str,
        user_name: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> bool:
        """
        Publish a user event.

        Args:
            event_type: Event type (login, logout, registered, banned, etc.)
            user_key: User's public key
            user_name: User's display name
            details: Optional additional details
        """
        payload = {
            "event": event_type,
            "user_key": user_key,
            "user_name": user_name,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if details:
            payload.update(details)

        return await self.publish("user", payload)

    async def publish_system_event(
        self,
        event_type: str,
        details: Optional[dict] = None,
    ) -> bool:
        """
        Publish a system event.

        Args:
            event_type: Event type (backup, error, warning, etc.)
            details: Optional additional details
        """
        payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if details:
            payload.update(details)

        return await self.publish("system", payload)

    async def publish_stats(self, stats: dict) -> bool:
        """
        Publish BBS statistics.

        Args:
            stats: Statistics dictionary
        """
        payload = {
            **stats,
            "timestamp": datetime.utcnow().isoformat(),
        }
        return await self.publish("stats", payload, retain=True)

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._connected


# Singleton instance
_mqtt_client: Optional[MQTTClient] = None


def get_mqtt_client() -> MQTTClient:
    """Get the global MQTT client instance."""
    global _mqtt_client
    if _mqtt_client is None:
        _mqtt_client = MQTTClient()
    return _mqtt_client


async def init_mqtt() -> Optional[MQTTClient]:
    """Initialize and connect the MQTT client."""
    client = get_mqtt_client()
    if client.config.enabled:
        await client.connect()
        return client
    return None


async def shutdown_mqtt() -> None:
    """Shutdown the MQTT client."""
    global _mqtt_client
    if _mqtt_client:
        await _mqtt_client.disconnect()
        _mqtt_client = None
