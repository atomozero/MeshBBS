"""
MeshCore connection management.

MIT License - Copyright (c) 2026 MeshBBS Contributors

This module provides the connection interface to MeshCore companion radios.
It includes both a real implementation using meshcore_py and a mock for testing.
"""

import asyncio
import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Awaitable, List, Any, Tuple
import uuid

from .messages import Message, Advert, Ack
from .protocol import PacketType, NodeType

# Import meshcore library (pip package).
# No longer conflicts since we renamed our local package to "meshbbs_radio".
try:
    from meshcore import MeshCore, EventType
    MESHCORE_AVAILABLE = True
except ImportError:
    MESHCORE_AVAILABLE = False
    MeshCore = None
    EventType = None

# Transport classes (used to build a MeshCore instance we can always clean
# up, even when the handshake fails or times out half-way).
try:
    from meshcore import TCPConnection, SerialConnection
except ImportError:
    TCPConnection = None
    SerialConnection = None

try:
    from meshcore import BLEConnection
except ImportError:
    BLEConnection = None

# Handle import based on context (standalone vs package)
try:
    from utils.logger import get_logger
    logger = get_logger("meshbbs.meshcore")
except ImportError:
    import logging
    logger = logging.getLogger("meshbbs.meshcore")

try:
    from utils.config import get_config
except ImportError:
    get_config = None


# path_len value used by the companion for direct-routed packets: the hop
# count is not reported in that case (the packet followed a known path).
PATH_LEN_DIRECT = 255


@dataclass
class Identity:
    """
    Represents the identity of this node.

    Contains the cryptographic identity used for MeshCore communication.
    """

    public_key: str
    name: str
    node_type: NodeType = NodeType.ROOM

    @property
    def short_key(self) -> str:
        """Get shortened public key for display."""
        return self.public_key[:8]


# Type alias for message callback
MessageCallback = Callable[[Message], Awaitable[None]]


def is_error_event(result: Any) -> bool:
    """
    Return True if a meshcore command result means failure.

    meshcore commands do not raise on timeout: they return
    Event(EventType.ERROR, ...) (or None for some helpers).
    """
    if result is None:
        return True
    if EventType is not None and getattr(result, "type", None) == EventType.ERROR:
        return True
    return False


def hops_from_payload(data: dict) -> int:
    """
    Extract the hop count from a meshcore 2.x message payload.

    meshcore reports ``path_len`` (number of path hashes = hops for flood
    packets). 255 means the packet was routed direct along a known path:
    the hop count is not available, so 0 is reported. Older libraries used
    a ``hops`` key, still accepted as fallback.
    """
    value = data.get("path_len")
    if value is None:
        value = data.get("hops", 0)
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    if value == PATH_LEN_DIRECT or value < 0:
        return 0
    return value


def _payload_value(data: dict, *keys: str) -> Any:
    """Return the first non-None value among keys (e.g. 'SNR', 'snr')."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            return value
    return None


def split_channel_sender(text: str) -> Tuple[Optional[str], str]:
    """
    Split a channel (GRP_TXT) text into (sender_name, body).

    MeshCore channel messages carry no sender key: the sender name is
    prepended to the text as "Name: message". Returns (None, text) when
    no prefix is present.
    """
    if text and ": " in text:
        name, body = text.split(": ", 1)
        name = name.strip()
        if name:
            return name, body
    return None, text


class BaseMeshCoreConnection(ABC):
    """
    Abstract base class for MeshCore connections.

    Provides the interface that all connection implementations must follow.
    """

    # How long a get_contacts() fetch stays fresh before a new fetch is
    # triggered on the next send. Lookups within this window reuse the
    # contact map already in self._meshcore.contacts, avoiding redundant
    # companion-radio round-trips between chunks of the same response.
    CONTACTS_CACHE_TTL = 30.0  # seconds

    # Maximum number of received messages waiting to be processed. When
    # full, the oldest message is dropped (with a warning).
    MESSAGE_QUEUE_MAXSIZE = 100

    def __init__(self):
        self.identity: Optional[Identity] = None
        self.connected: bool = False
        self._message_callbacks: List[MessageCallback] = []
        self._running: bool = False
        self._contacts_last_fetch: float = 0.0
        self._meshcore: Optional[Any] = None
        self._link_lost_callback: Optional[Callable[[str], Any]] = None
        self._advert_callback: Optional[Callable[[dict], Any]] = None
        self._dropped_messages: int = 0

    async def _refresh_contacts_if_stale(self) -> bool:
        """
        Fetch contacts from the companion only if the cache is stale.

        Returns True on success (or cache hit), False if fetch errored.
        """
        now = time.monotonic()
        if now - self._contacts_last_fetch < self.CONTACTS_CACHE_TTL:
            return True
        if self._meshcore is None:
            return False
        try:
            result = await self._meshcore.commands.get_contacts()
            if is_error_event(result):
                return False
            self._contacts_last_fetch = now
            return True
        except Exception:
            return False

    def _invalidate_contacts_cache(self) -> None:
        """Force a fresh fetch on the next send (e.g. after a failure)."""
        self._contacts_last_fetch = 0.0

    async def refresh_contacts(self, force: bool = False) -> bool:
        """
        Refresh the companion contact list.

        Args:
            force: Ignore the cache TTL and always fetch

        Returns:
            True on success (or cache hit), False on failure
        """
        if force:
            self._invalidate_contacts_cache()
        return await self._refresh_contacts_if_stale()

    def _enqueue_message(self, message: Message) -> None:
        """
        Put a received message in the bounded queue, dropping the oldest
        one if the queue is full (a stuck consumer must not grow memory).
        """
        queue = self._message_queue
        while True:
            try:
                queue.put_nowait(message)
                return
            except asyncio.QueueFull:
                try:
                    dropped = queue.get_nowait()
                    self._dropped_messages += 1
                    logger.warning(
                        f"Message queue full ({queue.maxsize}): dropped oldest "
                        f"message from {dropped.sender_short}"
                    )
                except asyncio.QueueEmpty:
                    pass

    def set_link_lost_callback(self, callback: Optional[Callable[[str], Any]]) -> None:
        """
        Register a callback invoked (with a reason) when the transport
        reports a disconnection, for immediate reconnect.
        """
        self._link_lost_callback = callback

    def set_advert_callback(self, callback: Optional[Callable[[dict], Any]]) -> None:
        """
        Register a callback invoked for every advert heard by the companion.

        It receives a dict with public_key and, when known, name, type,
        path_len (hops, -1 = unknown), lat and lon.
        """
        self._advert_callback = callback

    def _notify_advert(self, info: dict) -> None:
        callback = self._advert_callback
        if callback is None or not info.get("public_key"):
            return
        try:
            result = callback(info)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)
        except Exception as e:
            logger.error(f"Error in advert callback: {e}")

    def _notify_link_lost(self, reason: str) -> None:
        """Mark the link as down and notify the registered callback."""
        self.connected = False
        callback = self._link_lost_callback
        if callback is None:
            return
        try:
            result = callback(reason)
            if asyncio.iscoroutine(result):
                asyncio.ensure_future(result)
        except Exception as e:
            logger.error(f"Error in link-lost callback: {e}")

    async def probe(self) -> bool:
        """
        Check that the companion radio actually answers.

        Returns:
            True if the link is alive
        """
        return self.connected

    async def send_channel_message(self, channel_idx: int, text: str) -> bool:
        """
        Send a text message on a channel (GRP_TXT).

        Returns:
            True if the companion accepted the message
        """
        return False

    def flush_pending_contacts(self) -> int:
        """
        Drop pending (not yet added) contacts kept in memory by meshcore.

        Returns:
            Number of pending contacts dropped
        """
        return 0

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the companion radio.

        Returns:
            True if connection successful
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        pass

    @abstractmethod
    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Send a text message to a destination.

        Args:
            destination: Recipient's public key
            text: Message text
            use_path: Whether to use known path (if available)

        Returns:
            True if message was sent successfully
        """
        pass

    @abstractmethod
    async def send_advert(self, flood: bool = False) -> bool:
        """
        Send an advertisement announcing this node.

        Args:
            flood: Whether to flood through repeaters

        Returns:
            True if advert was sent
        """
        pass

    @abstractmethod
    async def receive(self) -> Optional[Message]:
        """
        Receive a message (blocking).

        Returns:
            Received message or None on timeout
        """
        pass

    def on_message(self, callback: MessageCallback) -> None:
        """
        Register a callback for incoming messages.

        Args:
            callback: Async function to call with received messages
        """
        self._message_callbacks.append(callback)

    async def _notify_message(self, message: Message) -> None:
        """Notify all registered callbacks of a new message."""
        for callback in self._message_callbacks:
            try:
                await callback(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.connected


class _LibraryMeshCoreConnection(BaseMeshCoreConnection):
    """
    Shared implementation for real companion radios driven by meshcore_py.

    Subclasses only describe the transport (serial, BLE, TCP) by building
    an unconnected MeshCore instance in _build_meshcore().

    All request/response commands sent to the companion are serialised by
    an asyncio.Lock installed on the MeshCore command handler: meshcore
    matches responses only by event type (MSG_SENT, OK, ERROR...), so two
    concurrent commands could otherwise receive each other's response.
    The lock wraps the single low-level send primitive, so it also covers
    callers using mc.commands directly (web admin, repeater monitor,
    meshcore's own message auto-fetch) and can never be acquired twice by
    the same call chain.
    """

    TRANSPORT_NAME = "MeshCore"

    # Max time for transport connect + appstart handshake
    CONNECT_TIMEOUT = 15.0

    # Max time for the cleanup of a failed/dead MeshCore instance
    CLEANUP_TIMEOUT = 5.0

    # Max time for a liveness probe (includes waiting for the command lock)
    PROBE_TIMEOUT = 20.0

    def __init__(
        self,
        timeout: float,
        use_mock_fallback: bool,
        debug: bool,
    ):
        super().__init__()
        self.timeout = timeout
        self.debug = debug
        self._use_mock_fallback = use_mock_fallback

        # MeshCore instance
        self._meshcore: Optional[Any] = None
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue(
            maxsize=self.MESSAGE_QUEUE_MAXSIZE
        )
        self._subscription = None
        self._channel_subscription = None
        self._disconnect_subscription = None
        self._advert_subscription = None
        self._new_contact_subscription = None
        self._auto_fetch_running = False
        self._command_lock: Optional[asyncio.Lock] = None

        # Fallback mock (only when explicitly enabled)
        self._mock: Optional[MockMeshCoreConnection] = None

        # Check if meshcore is available
        if not MESHCORE_AVAILABLE:
            if use_mock_fallback:
                logger.warning(
                    f"meshcore library not available for {self.TRANSPORT_NAME}. "
                    "Install with: pip install meshcore. "
                    "Using mock for development."
                )
                self._mock = MockMeshCoreConnection()
            else:
                raise ImportError(
                    "meshcore library is required. Install with: pip install meshcore"
                )

    # ------------------------------------------------------------------
    # Transport-specific hooks
    # ------------------------------------------------------------------

    @property
    def endpoint(self) -> str:
        """Human readable transport endpoint."""
        return self.TRANSPORT_NAME

    def _build_meshcore(self) -> Any:
        """Build an unconnected MeshCore instance for this transport."""
        raise NotImplementedError

    @property
    def _connect_timeout(self) -> float:
        return self.CONNECT_TIMEOUT

    # ------------------------------------------------------------------
    # Command serialisation
    # ------------------------------------------------------------------

    def _install_command_lock(self, mc: Any) -> None:
        """
        Serialise request/response commands of a MeshCore instance.

        Wraps mc.commands.send (the primitive every command uses). Only
        commands that wait for a response take the lock; fire-and-forget
        sends have no response that could be stolen.
        """
        lock = asyncio.Lock()
        self._command_lock = lock
        commands = mc.commands
        original_send = commands.send

        async def locked_send(data, expected_events=None, timeout=None):
            if not expected_events:
                return await original_send(data, expected_events, timeout)
            async with lock:
                return await original_send(data, expected_events, timeout)

        commands.send = locked_send

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def _cleanup_meshcore(self, mc: Any) -> None:
        """Best-effort release of a MeshCore instance (never raises)."""
        if mc is None:
            return
        try:
            transport_up = bool(getattr(mc, "is_connected", False))
        except Exception:
            transport_up = False
        try:
            await asyncio.wait_for(mc.disconnect(), timeout=self.CLEANUP_TIMEOUT)
        except Exception as e:
            logger.debug(f"{self.TRANSPORT_NAME} cleanup: disconnect failed: {e}")
            try:
                mc.stop()
            except Exception:
                pass
        if not transport_up:
            # The connection manager only closes the transport when the
            # handshake completed: close it explicitly otherwise.
            cx = getattr(getattr(mc, "connection_manager", None), "connection", None)
            if cx is not None and hasattr(cx, "disconnect"):
                try:
                    await asyncio.wait_for(cx.disconnect(), timeout=self.CLEANUP_TIMEOUT)
                except Exception:
                    pass

    def _identity_from_self_info(self, info: Any) -> Identity:
        """Build our Identity from meshcore self_info."""
        if not info or not isinstance(info, dict):
            logger.warning("Could not get device identity, using default")
            return Identity(public_key="0" * 64, name="MeshBBS", node_type=NodeType.ROOM)
        public_key = info.get("public_key")
        if public_key is None:
            public_key = info.get("pubkey", "")  # older meshcore versions
        if isinstance(public_key, bytes):
            public_key = public_key.hex()
        return Identity(
            public_key=public_key or "0" * 64,
            name=info.get("name", "Unknown"),
            node_type=NodeType.ROOM,
        )

    async def connect(self) -> bool:
        """
        Connect to the companion radio.

        On failure the state is left disconnected (no automatic mock
        fallback unless explicitly enabled) so the caller can retry.

        Returns:
            True if connection successful
        """
        # If using mock fallback
        if self._mock is not None:
            result = await self._mock.connect()
            self.identity = self._mock.identity
            self.connected = self._mock.connected
            return result

        # Never leak a previous instance
        if self._meshcore is not None:
            await self.disconnect()

        mc = None
        try:
            logger.info(f"Connecting to MeshCore device via {self.endpoint}...")

            mc = self._build_meshcore()
            self._install_command_lock(mc)

            appstart = await asyncio.wait_for(mc.connect(), timeout=self._connect_timeout)
            if appstart is None or is_error_event(appstart):
                raise ConnectionError("no response from companion (appstart)")

            # Get device identity from self_info (the SELF_INFO tracking
            # callback runs as a task, so fall back to the appstart payload)
            info = mc.self_info or getattr(appstart, "payload", None)
            self.identity = self._identity_from_self_info(info)

            # Subscribe to incoming messages
            self._subscription = mc.subscribe(
                EventType.CONTACT_MSG_RECV,
                self._on_private_message
            )

            # Subscribe to channel messages
            self._channel_subscription = mc.subscribe(
                EventType.CHANNEL_MSG_RECV,
                self._on_channel_message
            )

            # Immediate dead-link detection
            self._disconnect_subscription = mc.subscribe(
                EventType.DISCONNECTED,
                self._make_disconnect_handler(mc),
            )

            # Adverts heard by the companion (node history, deferred
            # notifications). ADVERTISEMENT carries only the key; the
            # contact details come from the contact list.
            self._advert_subscription = mc.subscribe(
                EventType.ADVERTISEMENT, self._on_advert_event
            )
            self._new_contact_subscription = mc.subscribe(
                EventType.NEW_CONTACT, self._on_advert_event
            )

            self._meshcore = mc

            # Load contacts now: DM replies and repeater polling need them
            self._invalidate_contacts_cache()
            if not await self._refresh_contacts_if_stale():
                logger.warning("Could not load contacts from companion (will retry)")

            # Start auto-fetching messages
            await mc.start_auto_message_fetching()
            self._auto_fetch_running = True

            self.connected = True
            logger.info(
                f"Connected to MeshCore {self.TRANSPORT_NAME} device: "
                f"{self.identity.name} ({self.identity.short_key}...)"
            )
            return True

        except Exception as e:
            reason = str(e) or type(e).__name__
            logger.error(f"Failed to connect to MeshCore {self.TRANSPORT_NAME} device: {reason}")
            self._reset_subscriptions(mc)
            self._meshcore = None
            self._auto_fetch_running = False
            self.connected = False
            await self._cleanup_meshcore(mc)

            # Fall back to mock only if explicitly enabled
            if self._use_mock_fallback and self._mock is None:
                logger.warning("Falling back to mock implementation")
                self._mock = MockMeshCoreConnection()
                result = await self._mock.connect()
                self.identity = self._mock.identity
                self.connected = self._mock.connected
                return result

            return False

    def _make_disconnect_handler(self, mc: Any):
        async def _on_disconnected(event: Any) -> None:
            if self._meshcore is not mc:
                return  # stale instance
            payload = getattr(event, "payload", None) or {}
            reason = payload.get("reason", "unknown") if isinstance(payload, dict) else "unknown"
            if reason == "manual_disconnect":
                return
            logger.warning(f"{self.TRANSPORT_NAME} link lost: {reason}")
            self._notify_link_lost(reason)
        return _on_disconnected

    def _reset_subscriptions(self, mc: Any) -> None:
        for attr in ("_subscription", "_channel_subscription", "_disconnect_subscription",
                     "_advert_subscription", "_new_contact_subscription"):
            sub = getattr(self, attr)
            if sub is not None and mc is not None:
                try:
                    mc.unsubscribe(sub)
                except Exception:
                    pass
            setattr(self, attr, None)

    async def disconnect(self) -> None:
        """Disconnect from companion radio."""
        if self._mock is not None:
            await self._mock.disconnect()
            self.connected = False
            return

        mc = self._meshcore
        self._meshcore = None
        self.connected = False

        if mc:
            try:
                # Stop auto-fetching
                if self._auto_fetch_running:
                    self._auto_fetch_running = False
                    await asyncio.wait_for(
                        mc.stop_auto_message_fetching(), timeout=self.CLEANUP_TIMEOUT
                    )
            except Exception as e:
                logger.error(f"Error during {self.TRANSPORT_NAME} disconnect: {e}")

            self._reset_subscriptions(mc)
            await self._cleanup_meshcore(mc)
            logger.info(f"MeshCore {self.TRANSPORT_NAME} connection closed")

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Send a text message to a destination.

        Args:
            destination: Recipient's public key or key prefix (hex string)
            text: Message text
            use_path: Whether to use known path (currently unused)

        Returns:
            True if message was sent (ACKed) successfully
        """
        if self._mock is not None:
            return await self._mock.send_message(destination, text, use_path)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send: not connected")
            return False

        try:
            await self._refresh_contacts_if_stale()

            mc = self._meshcore
            if mc is None:
                return False
            contact = mc.get_contact_by_key_prefix(destination[:12])
            target = contact if contact else (
                bytes.fromhex(destination) if len(destination) == 64 else destination
            )

            config = get_config() if get_config else None
            max_attempts = config.max_send_attempts if config else 3
            retry_delay = config.send_retry_delay if config else 2.0

            send_result = await self._send_with_backoff(
                target, text, max_attempts, retry_delay,
            )

            if not send_result:
                logger.error(f"Send failed to={destination[:12]}")
                self._invalidate_contacts_cache()
                return False

            logger.info(f"SENT to={destination[:12]} len={len(text)}")
            return True

        except Exception as e:
            logger.error(f"Error sending message via {self.TRANSPORT_NAME}: {e}")
            self._invalidate_contacts_cache()
            return False

    async def _send_with_backoff(
        self, contact, text: str, max_attempts: int, retry_delay: float,
    ) -> bool:
        """
        Send message via send_msg_with_retry.

        Delegates to meshcore's send_msg_with_retry which handles ACK waiting,
        path reset, and automatic flood fallback when the direct path fails —
        needed so users multiple hops away receive DM replies even when we
        have no prior out_path for them.
        """
        try:
            result = await self._meshcore.commands.send_msg_with_retry(
                contact, text,
                max_attempts=max_attempts,
                max_flood_attempts=2,
                flood_after=1,
            )
            if is_error_event(result):
                logger.error("send_msg_with_retry exhausted all attempts")
                return False
            return True
        except Exception as e:
            logger.error(f"send_msg_with_retry error: {e}")
            return False

    async def send_advert(self, flood: bool = False) -> bool:
        """
        Send an advertisement announcing this node.

        The companion's flood scope (region) is left untouched.

        Args:
            flood: Whether to flood through repeaters

        Returns:
            True if advert was sent
        """
        if self._mock is not None:
            return await self._mock.send_advert(flood)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send advert: not connected")
            return False

        try:
            result = await self._meshcore.commands.send_advert(flood=flood)

            if is_error_event(result):
                payload = getattr(result, "payload", None)
                logger.error(f"Failed to send advert: {payload}")
                return False

            flood_str = "flood" if flood else "zero-hop"
            logger.info(f"{self.TRANSPORT_NAME} advertisement sent ({flood_str})")
            return True

        except Exception as e:
            logger.error(f"Error sending advert via {self.TRANSPORT_NAME}: {e}")
            return False

    async def send_channel_message(self, channel_idx: int, text: str) -> bool:
        """Send a text message on a channel. Returns True if accepted."""
        if self._mock is not None:
            return await self._mock.send_channel_message(channel_idx, text)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send channel message: not connected")
            return False

        try:
            result = await self._meshcore.commands.send_chan_msg(channel_idx, text)
            if is_error_event(result):
                payload = getattr(result, "payload", None)
                logger.error(f"Channel message rejected: {payload}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error sending channel message via {self.TRANSPORT_NAME}: {e}")
            return False

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def probe(self) -> bool:
        """
        Cheap liveness check: ask the companion for its battery level.

        A dead TCP link does not raise: the command simply times out and
        returns an ERROR event, which is treated as failure here.
        """
        if self._mock is not None:
            return self._mock.connected

        mc = self._meshcore
        if not self.connected or mc is None:
            return False
        if not getattr(mc, "is_connected", True):
            return False

        try:
            result = await asyncio.wait_for(
                mc.commands.get_bat(), timeout=self.PROBE_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"{self.TRANSPORT_NAME} probe failed: {e}")
            return False

        if is_error_event(result):
            logger.warning(
                f"{self.TRANSPORT_NAME} probe failed: "
                f"{getattr(result, 'payload', None)}"
            )
            return False
        return True

    def flush_pending_contacts(self) -> int:
        """Drop pending contacts accumulated by meshcore (memory bound)."""
        mc = self._meshcore
        if mc is None:
            return 0
        try:
            count = len(getattr(mc, "pending_contacts", None) or {})
        except Exception:
            count = 0
        flush = getattr(mc, "flush_pending_contacts", None)
        if callable(flush):
            try:
                flush()
            except Exception as e:
                logger.debug(f"flush_pending_contacts failed: {e}")
                return 0
        return count

    # ------------------------------------------------------------------
    # Receiving
    # ------------------------------------------------------------------

    async def receive(self) -> Optional[Message]:
        """
        Receive a message from the queue.

        Returns:
            Received message or None on timeout
        """
        if self._mock is not None:
            return await self._mock.receive()

        try:
            message = await asyncio.wait_for(
                self._message_queue.get(),
                timeout=self.timeout,
            )
            await self._notify_message(message)
            return message

        except asyncio.TimeoutError:
            return None

    async def _on_private_message(self, event: Any) -> None:
        """
        Handle incoming private message event from meshcore.

        Args:
            event: MeshCore event containing message data
        """
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()
            sender_key = (sender_key or '').lower()

            text = data.get('text', '')

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                recipient_key=self.identity.public_key if self.identity else None,
                hops=hops_from_payload(data),
                rssi=_payload_value(data, 'RSSI', 'rssi'),
                snr=_payload_value(data, 'SNR', 'snr'),
            )

            self._enqueue_message(message)
            logger.debug(f"Received private message from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing private message: {e}")

    async def _on_advert_event(self, event: Any) -> None:
        """Handle ADVERTISEMENT / NEW_CONTACT push events from meshcore."""
        try:
            data = getattr(event, "payload", None) or {}
            if not isinstance(data, dict):
                return
            key = data.get("public_key", "")
            if isinstance(key, bytes):
                key = key.hex()
            key = (key or "").lower()
            if not key:
                return
            contact = data if "adv_name" in data else None
            mc = self._meshcore
            if contact is None and mc is not None:
                try:
                    contact = (getattr(mc, "contacts", None) or {}).get(key) or \
                        (getattr(mc, "pending_contacts", None) or {}).get(key)
                except Exception:
                    contact = None
            contact = contact or {}
            path_len = contact.get("out_path_len")
            self._notify_advert({
                "public_key": key,
                "name": contact.get("adv_name") or None,
                "type": contact.get("type"),
                "path_len": path_len if isinstance(path_len, int) and path_len >= 0 else None,
                "lat": contact.get("adv_lat"),
                "lon": contact.get("adv_lon"),
            })
        except Exception as e:
            logger.error(f"Error processing advert: {e}")

    async def _on_channel_message(self, event: Any) -> None:
        """
        Handle incoming channel message event from meshcore (GRP_TXT).

        Channel messages have no sender key: the sender name is parsed
        from the "Name: text" prefix and stored in Message.sender_name,
        while Message.text keeps only the body.

        Args:
            event: MeshCore event containing channel message data
        """
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()
            sender_key = (sender_key or '').lower()

            raw_text = data.get('text', '')
            sender_name, text = split_channel_sender(raw_text)
            channel_idx = data.get('channel_idx', 0)

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                hops=hops_from_payload(data),
                rssi=_payload_value(data, 'RSSI', 'rssi'),
                snr=_payload_value(data, 'SNR', 'snr'),
                sender_name=sender_name,
                channel_idx=channel_idx,
                is_group_message=True,
            )

            self._enqueue_message(message)
            logger.debug(
                f"Received group message on channel {channel_idx} "
                f"from {message.sender_short}"
            )

        except Exception as e:
            logger.error(f"Error processing channel message: {e}")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_contacts(self) -> List[dict]:
        """
        Get list of known contacts from the device.

        Returns:
            List of contact dictionaries
        """
        if self._mock is not None:
            return []

        if not self.connected or not self._meshcore:
            return []

        try:
            result = await self._meshcore.commands.get_contacts()
            if not is_error_event(result):
                self._contacts_last_fetch = time.monotonic()
                return list(result.payload.values())
        except Exception as e:
            logger.error(f"Error getting contacts via {self.TRANSPORT_NAME}: {e}")

        return []

    async def get_battery(self) -> Optional[dict]:
        """
        Get battery status from the device.

        Returns:
            Battery info dictionary or None
        """
        if self._mock is not None:
            return {"level": 100, "charging": False}

        if not self.connected or not self._meshcore:
            return None

        try:
            result = await self._meshcore.commands.get_bat()
            if not is_error_event(result):
                return result.payload
        except Exception as e:
            logger.error(f"Error getting battery via {self.TRANSPORT_NAME}: {e}")

        return None

    @property
    def is_using_mock(self) -> bool:
        """Check if currently using mock implementation."""
        return self._mock is not None


class MeshCoreConnection(_LibraryMeshCoreConnection):
    """
    Real MeshCore connection via serial port using meshcore_py library.

    This is the production implementation that communicates with a real
    MeshCore companion radio device.
    """

    TRANSPORT_NAME = "serial"

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        timeout: float = 1.0,
        use_mock_fallback: bool = False,
        debug: bool = False,
    ):
        """
        Initialize MeshCore connection.

        Args:
            port: Serial port path (e.g., /dev/ttyUSB0, COM3)
            baud_rate: Serial baud rate (default 115200)
            timeout: Receive timeout in seconds
            use_mock_fallback: If True, fall back to mock when the radio is
                unavailable (development only, never in production)
            debug: Enable debug logging in meshcore library
        """
        self.port = port
        self.baud_rate = baud_rate
        super().__init__(timeout=timeout, use_mock_fallback=use_mock_fallback, debug=debug)

    @property
    def endpoint(self) -> str:
        return self.port

    def _build_meshcore(self) -> Any:
        return MeshCore(SerialConnection(self.port, self.baud_rate, cx_dly=0.1), debug=self.debug)


class BLEMeshCoreConnection(_LibraryMeshCoreConnection):
    """
    MeshCore connection via Bluetooth Low Energy (BLE).

    Connects to MeshCore companion radio devices over BLE.
    Requires the device to be paired with the host system.
    """

    TRANSPORT_NAME = "BLE"

    def __init__(
        self,
        address: Optional[str] = None,
        pin: Optional[str] = None,
        timeout: float = 30.0,
        use_mock_fallback: bool = False,
        debug: bool = False,
    ):
        """
        Initialize BLE MeshCore connection.

        Args:
            address: BLE device address (e.g., "12:34:56:78:90:AB").
                    If None, will scan for available devices.
            pin: Optional PIN for secure pairing (6 digits).
            timeout: Connection timeout in seconds.
            use_mock_fallback: If True, fall back to mock when BLE unavailable.
            debug: Enable debug logging in meshcore library.
        """
        self.address = address
        self.pin = pin
        super().__init__(timeout=timeout, use_mock_fallback=use_mock_fallback, debug=debug)

    @property
    def endpoint(self) -> str:
        return f"BLE {self.address}" if self.address else "BLE (scan)"

    @property
    def _connect_timeout(self) -> float:
        # BLE scanning/pairing is slower than serial/TCP
        return max(self.CONNECT_TIMEOUT, float(self.timeout))

    def _build_meshcore(self) -> Any:
        if self.pin:
            logger.info("Using PIN authentication for BLE connection")
        return MeshCore(BLEConnection(address=self.address, pin=self.pin), debug=self.debug)

    async def set_device_pin(self, pin: int) -> bool:
        """
        Set the device PIN for secure BLE pairing.

        Args:
            pin: 6-digit PIN code

        Returns:
            True if PIN was set successfully
        """
        if self._mock is not None:
            return True

        if not self.connected or not self._meshcore:
            logger.error("Cannot set PIN: not connected")
            return False

        try:
            result = await self._meshcore.commands.set_devicepin(pin)
            if not is_error_event(result):
                logger.info("Device PIN set successfully")
                return True
            else:
                logger.error(f"Failed to set device PIN: {result.payload}")
                return False
        except Exception as e:
            logger.error(f"Error setting device PIN: {e}")
            return False


class TCPMeshCoreConnection(_LibraryMeshCoreConnection):
    """
    MeshCore connection via TCP/IP.

    Connects to MeshCore companion radio devices over WiFi/Ethernet
    using TCP sockets. Useful for ESP32 nodes with WiFi capability.
    """

    TRANSPORT_NAME = "TCP"

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 5000,
        timeout: float = 30.0,
        use_mock_fallback: bool = False,
        debug: bool = False,
    ):
        """
        Initialize TCP MeshCore connection.

        Args:
            host: IP address or hostname of the MeshCore device.
            port: TCP port number (default 5000).
            timeout: Receive timeout in seconds.
            use_mock_fallback: If True, fall back to mock when TCP unavailable
                (development only, never in production).
            debug: Enable debug logging in meshcore library.
        """
        self.host = host
        self.port = port
        super().__init__(timeout=timeout, use_mock_fallback=use_mock_fallback, debug=debug)

    def _build_meshcore(self) -> Any:
        return MeshCore(TCPConnection(self.host, self.port), debug=self.debug)

    @property
    def endpoint(self) -> str:
        """Get the TCP endpoint string."""
        return f"{self.host}:{self.port}"


class MockMeshCoreConnection(BaseMeshCoreConnection):
    """
    Mock MeshCore connection for testing without hardware.

    Simulates a companion radio for development and testing.
    """

    def __init__(self, node_name: str = "MockBBS"):
        super().__init__()
        self.node_name = node_name
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue(
            maxsize=self.MESSAGE_QUEUE_MAXSIZE
        )
        self._sent_messages: List[Message] = []
        self._sent_channel_messages: List[Tuple[int, str]] = []

        # Generate mock identity
        self.identity = Identity(
            public_key="MOCK" + "0" * 60,  # 64 char mock key
            name=node_name,
            node_type=NodeType.ROOM,
        )

    async def connect(self) -> bool:
        """Simulate connection."""
        logger.info(f"Mock connection established for {self.node_name}")
        self.connected = True
        return True

    async def disconnect(self) -> None:
        """Simulate disconnection."""
        logger.info("Mock connection closed")
        self.connected = False

    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Simulate sending a message.

        The message is stored for inspection in tests.
        """
        if not self.connected:
            logger.error("Cannot send: not connected")
            return False

        message = Message(
            sender_key=self.identity.public_key,
            recipient_key=destination,
            text=text,
            timestamp=datetime.utcnow(),
            message_id=str(uuid.uuid4())[:8],
        )

        self._sent_messages.append(message)
        logger.debug(f"Mock sent to {destination[:8]}: {text[:30]}...")

        return True

    async def send_advert(self, flood: bool = False) -> bool:
        """Simulate sending an advertisement."""
        if not self.connected:
            return False

        flood_str = "flood" if flood else "zero-hop"
        logger.info(f"Mock advert sent ({flood_str}): {self.node_name}")
        return True

    async def send_channel_message(self, channel_idx: int, text: str) -> bool:
        """Simulate sending a channel message (stored for inspection)."""
        if not self.connected:
            return False
        self._sent_channel_messages.append((channel_idx, text))
        logger.debug(f"Mock channel {channel_idx} message: {text[:30]}...")
        return True

    async def receive(self) -> Optional[Message]:
        """
        Receive a message from the queue.

        In mock mode, messages must be injected via inject_message().
        """
        try:
            message = await asyncio.wait_for(
                self._message_queue.get(),
                timeout=1.0,
            )
            await self._notify_message(message)
            return message
        except asyncio.TimeoutError:
            return None

    async def inject_message(
        self,
        sender_key: str,
        text: str,
        hops: int = 0,
        rssi: Optional[int] = None,
    ) -> None:
        """
        Inject a message into the receive queue (for testing).

        Args:
            sender_key: Simulated sender's public key
            text: Message text
            hops: Simulated hop count
            rssi: Simulated signal strength
        """
        message = Message(
            sender_key=sender_key,
            text=text,
            timestamp=datetime.utcnow(),
            recipient_key=self.identity.public_key,
            hops=hops,
            rssi=rssi,
        )
        self._enqueue_message(message)
        logger.debug(f"Injected message from {sender_key[:8]}: {text[:30]}...")

    def get_sent_messages(self) -> List[Message]:
        """Get all messages sent through this mock connection."""
        return self._sent_messages.copy()

    def clear_sent_messages(self) -> None:
        """Clear the sent messages list."""
        self._sent_messages.clear()
