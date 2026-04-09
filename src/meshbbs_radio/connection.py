"""
MeshCore connection management.

MIT License - Copyright (c) 2026 MeshBBS Contributors

This module provides the connection interface to MeshCore companion radios.
It includes both a real implementation using meshcore_py and a mock for testing.
"""

import asyncio
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, Awaitable, List, Any
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


class BaseMeshCoreConnection(ABC):
    """
    Abstract base class for MeshCore connections.

    Provides the interface that all connection implementations must follow.
    """

    def __init__(self):
        self.identity: Optional[Identity] = None
        self.connected: bool = False
        self._message_callbacks: List[MessageCallback] = []
        self._running: bool = False

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


class MeshCoreConnection(BaseMeshCoreConnection):
    """
    Real MeshCore connection via serial port using meshcore_py library.

    This is the production implementation that communicates with a real
    MeshCore companion radio device.
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baud_rate: int = 115200,
        timeout: float = 1.0,
        use_mock_fallback: bool = True,
        debug: bool = False,
    ):
        """
        Initialize MeshCore connection.

        Args:
            port: Serial port path (e.g., /dev/ttyUSB0, COM3)
            baud_rate: Serial baud rate (default 115200)
            timeout: Connection timeout in seconds
            use_mock_fallback: If True, fall back to mock when meshcore unavailable
            debug: Enable debug logging in meshcore library
        """
        super().__init__()
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.debug = debug
        self._use_mock_fallback = use_mock_fallback

        # MeshCore instance
        self._meshcore: Optional[Any] = None
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._subscription = None
        self._channel_subscription = None
        self._auto_fetch_running = False

        # Fallback mock
        self._mock: Optional[MockMeshCoreConnection] = None

        # Resolve meshcore library (lazy load)

        # Check if meshcore is available
        if not MESHCORE_AVAILABLE:
            if use_mock_fallback:
                logger.warning(
                    "meshcore library not available. "
                    "Install with: pip install meshcore. "
                    "Using mock for development."
                )
                self._mock = MockMeshCoreConnection()
            else:
                raise ImportError(
                    "meshcore library is required. Install with: pip install meshcore"
                )

    async def connect(self) -> bool:
        """
        Connect to companion radio via serial port.

        Returns:
            True if connection successful
        """
        # If using mock fallback
        if self._mock is not None:
            result = await self._mock.connect()
            self.identity = self._mock.identity
            self.connected = self._mock.connected
            return result

        try:
            logger.info(f"Connecting to MeshCore device on {self.port}...")

            # Create serial connection using meshcore_py
            self._meshcore = await MeshCore.create_serial(
                self.port,
                self.baud_rate,
                debug=self.debug
            )

            # Get device identity from self_info
            if self._meshcore.self_info:
                self.identity = Identity(
                    public_key=self._meshcore.self_info.get('pubkey', '').hex()
                        if isinstance(self._meshcore.self_info.get('pubkey'), bytes)
                        else self._meshcore.self_info.get('pubkey', ''),
                    name=self._meshcore.self_info.get('name', 'Unknown'),
                    node_type=NodeType.ROOM,
                )
                logger.info(
                    f"Connected to MeshCore device: {self.identity.name} "
                    f"({self.identity.short_key}...)"
                )
            else:
                # Create default identity
                self.identity = Identity(
                    public_key="0" * 64,
                    name="MeshBBS",
                    node_type=NodeType.ROOM,
                )
                logger.warning("Could not get device identity, using default")

            # Subscribe to incoming messages
            self._subscription = self._meshcore.subscribe(
                EventType.CONTACT_MSG_RECV,
                self._on_private_message
            )

            # Subscribe to channel messages
            self._channel_subscription = self._meshcore.subscribe(
                EventType.CHANNEL_MSG_RECV,
                self._on_channel_message
            )

            # Start auto-fetching messages
            await self._meshcore.start_auto_message_fetching()
            self._auto_fetch_running = True

            self.connected = True
            logger.info("MeshCore connection established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MeshCore device: {e}")

            # Fall back to mock if enabled
            if self._use_mock_fallback and self._mock is None:
                logger.warning("Falling back to mock implementation")
                self._mock = MockMeshCoreConnection()
                result = await self._mock.connect()
                self.identity = self._mock.identity
                self.connected = self._mock.connected
                return result

            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from companion radio."""
        if self._mock is not None:
            await self._mock.disconnect()
            self.connected = False
            return

        if self._meshcore:
            try:
                # Stop auto-fetching
                if self._auto_fetch_running:
                    await self._meshcore.stop_auto_message_fetching()
                    self._auto_fetch_running = False

                # Unsubscribe from events
                if self._subscription:
                    self._meshcore.unsubscribe(self._subscription)
                    self._subscription = None

                if self._channel_subscription:
                    self._meshcore.unsubscribe(self._channel_subscription)
                    self._channel_subscription = None

                # Disconnect
                await self._meshcore.disconnect()
                logger.info("MeshCore connection closed")

            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

            finally:
                self._meshcore = None

        self.connected = False

    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Send a text message to a destination.

        Args:
            destination: Recipient's public key (hex string)
            text: Message text
            use_path: Whether to use known path (currently unused)

        Returns:
            True if message was sent successfully
        """
        if self._mock is not None:
            return await self._mock.send_message(destination, text, use_path)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send: not connected")
            return False

        try:
            # Get contacts to find the destination
            result = await self._meshcore.commands.get_contacts()

            if result.type == EventType.ERROR:
                logger.error(f"Error getting contacts: {result.payload}")
                # Try sending directly with the public key
                contact = destination
            else:
                # Find contact by public key prefix
                contact = self._meshcore.get_contact_by_key_prefix(destination[:12])
                if not contact:
                    # Use the destination key directly
                    contact = bytes.fromhex(destination) if len(destination) == 64 else destination

            # Send message with retry and backoff for reliability
            config = get_config() if get_config else None
            max_attempts = config.max_send_attempts if config else 2
            retry_delay = config.send_retry_delay if config else 2.0

            send_result = await self._send_with_backoff(
                contact, text, max_attempts, retry_delay,
            )

            if not send_result:
                logger.error(f"Failed to send message to {destination[:8]}...")
                return False

            logger.debug(f"Message sent to {destination[:8]}...: {text[:30]}...")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def _send_with_backoff(
        self, contact, text: str, max_attempts: int, retry_delay: float,
    ) -> bool:
        """Send message with retry and backoff between attempts."""
        for attempt in range(1, max_attempts + 1):
            try:
                # Use simple send_msg first (faster, no ACK wait)
                send_result = await self._meshcore.commands.send_msg(contact, text)

                if send_result.type != EventType.ERROR:
                    return True
            except Exception as e:
                logger.warning(f"Send attempt {attempt}/{max_attempts} error: {e}")

            if attempt < max_attempts:
                delay = retry_delay * attempt
                logger.warning(
                    f"Send attempt {attempt}/{max_attempts} failed, "
                    f"retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        logger.error(f"All {max_attempts} send attempts failed")
        return False

    async def send_advert(self, flood: bool = False) -> bool:
        """
        Send an advertisement announcing this node.

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
            # Set flood scope if needed
            if flood:
                await self._meshcore.commands.set_flood_scope("*")

            # Send appstart to advertise presence
            result = await self._meshcore.commands.send_appstart()

            if result.type == EventType.ERROR:
                logger.error(f"Failed to send advert: {result.payload}")
                return False

            flood_str = "flood" if flood else "zero-hop"
            logger.info(f"Advertisement sent ({flood_str})")
            return True

        except Exception as e:
            logger.error(f"Error sending advert: {e}")
            return False

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

            # Extract message data
            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')

            # Create Message object
            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                recipient_key=self.identity.public_key if self.identity else None,
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
            )

            # Add to queue
            await self._message_queue.put(message)
            logger.debug(f"Received private message from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing private message: {e}")

    async def _on_channel_message(self, event: Any) -> None:
        """
        Handle incoming channel message event from meshcore (GRP_TXT).

        Args:
            event: MeshCore event containing channel message data
        """
        try:
            data = event.payload

            # Extract message data
            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')
            channel_idx = data.get('channel_idx', 0)

            # Create Message object with group message fields
            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
                channel_idx=channel_idx,
                is_group_message=True,
            )

            # Add to queue
            await self._message_queue.put(message)
            logger.debug(f"Received group message on channel {channel_idx} from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing channel message: {e}")

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
            if result.type != EventType.ERROR:
                return list(result.payload.values())
        except Exception as e:
            logger.error(f"Error getting contacts: {e}")

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
            if result.type != EventType.ERROR:
                return result.payload
        except Exception as e:
            logger.error(f"Error getting battery: {e}")

        return None

    @property
    def is_using_mock(self) -> bool:
        """Check if currently using mock implementation."""
        return self._mock is not None


class BLEMeshCoreConnection(BaseMeshCoreConnection):
    """
    MeshCore connection via Bluetooth Low Energy (BLE).

    Connects to MeshCore companion radio devices over BLE.
    Requires the device to be paired with the host system.
    """

    def __init__(
        self,
        address: Optional[str] = None,
        pin: Optional[str] = None,
        timeout: float = 30.0,
        use_mock_fallback: bool = True,
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
        super().__init__()
        self.address = address
        self.pin = pin
        self.timeout = timeout
        self.debug = debug
        self._use_mock_fallback = use_mock_fallback

        # MeshCore instance
        self._meshcore: Optional[Any] = None
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._subscription = None
        self._channel_subscription = None
        self._auto_fetch_running = False

        # Fallback mock
        self._mock: Optional[MockMeshCoreConnection] = None

        # Resolve meshcore library (lazy load)

        # Check if meshcore is available
        if not MESHCORE_AVAILABLE:
            if use_mock_fallback:
                logger.warning(
                    "meshcore library not available for BLE. "
                    "Install with: pip install meshcore. "
                    "Using mock for development."
                )
                self._mock = MockMeshCoreConnection()
            else:
                raise ImportError(
                    "meshcore library is required for BLE. Install with: pip install meshcore"
                )

    async def connect(self) -> bool:
        """
        Connect to companion radio via BLE.

        If no address is provided, scans for available devices.

        Returns:
            True if connection successful
        """
        # If using mock fallback
        if self._mock is not None:
            result = await self._mock.connect()
            self.identity = self._mock.identity
            self.connected = self._mock.connected
            return result

        try:
            if self.address:
                logger.info(f"Connecting to MeshCore device via BLE at {self.address}...")
            else:
                logger.info("Scanning for MeshCore BLE devices...")

            # Create BLE connection using meshcore_py
            if self.pin:
                logger.info("Using PIN authentication for BLE connection")
                self._meshcore = await MeshCore.create_ble(
                    self.address,
                    pin=self.pin,
                    debug=self.debug
                )
            else:
                self._meshcore = await MeshCore.create_ble(
                    self.address,
                    debug=self.debug
                )

            # Get device identity from self_info
            if self._meshcore.self_info:
                self.identity = Identity(
                    public_key=self._meshcore.self_info.get('pubkey', '').hex()
                        if isinstance(self._meshcore.self_info.get('pubkey'), bytes)
                        else self._meshcore.self_info.get('pubkey', ''),
                    name=self._meshcore.self_info.get('name', 'Unknown'),
                    node_type=NodeType.ROOM,
                )
                logger.info(
                    f"Connected to MeshCore BLE device: {self.identity.name} "
                    f"({self.identity.short_key}...)"
                )
            else:
                # Create default identity
                self.identity = Identity(
                    public_key="0" * 64,
                    name="MeshBBS",
                    node_type=NodeType.ROOM,
                )
                logger.warning("Could not get device identity, using default")

            # Subscribe to incoming messages
            self._subscription = self._meshcore.subscribe(
                EventType.CONTACT_MSG_RECV,
                self._on_private_message
            )

            # Subscribe to channel messages
            self._channel_subscription = self._meshcore.subscribe(
                EventType.CHANNEL_MSG_RECV,
                self._on_channel_message
            )

            # Start auto-fetching messages
            await self._meshcore.start_auto_message_fetching()
            self._auto_fetch_running = True

            self.connected = True
            logger.info("MeshCore BLE connection established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MeshCore BLE device: {e}")

            # Fall back to mock if enabled
            if self._use_mock_fallback and self._mock is None:
                logger.warning("Falling back to mock implementation")
                self._mock = MockMeshCoreConnection()
                result = await self._mock.connect()
                self.identity = self._mock.identity
                self.connected = self._mock.connected
                return result

            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from companion radio."""
        if self._mock is not None:
            await self._mock.disconnect()
            self.connected = False
            return

        if self._meshcore:
            try:
                # Stop auto-fetching
                if self._auto_fetch_running:
                    await self._meshcore.stop_auto_message_fetching()
                    self._auto_fetch_running = False

                # Unsubscribe from events
                if self._subscription:
                    self._meshcore.unsubscribe(self._subscription)
                    self._subscription = None

                if self._channel_subscription:
                    self._meshcore.unsubscribe(self._channel_subscription)
                    self._channel_subscription = None

                # Disconnect
                await self._meshcore.disconnect()
                logger.info("MeshCore BLE connection closed")

            except Exception as e:
                logger.error(f"Error during BLE disconnect: {e}")

            finally:
                self._meshcore = None

        self.connected = False

    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Send a text message to a destination.

        Args:
            destination: Recipient's public key (hex string)
            text: Message text
            use_path: Whether to use known path (currently unused)

        Returns:
            True if message was sent successfully
        """
        if self._mock is not None:
            return await self._mock.send_message(destination, text, use_path)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send: not connected")
            return False

        try:
            # Get contacts to find the destination
            result = await self._meshcore.commands.get_contacts()

            if result.type == EventType.ERROR:
                logger.error(f"Error getting contacts: {result.payload}")
                contact = destination
            else:
                # Find contact by public key prefix
                contact = self._meshcore.get_contact_by_key_prefix(destination[:12])
                if not contact:
                    contact = bytes.fromhex(destination) if len(destination) == 64 else destination

            # Send message with retry and backoff for reliability
            config = get_config() if get_config else None
            max_attempts = config.max_send_attempts if config else 2
            retry_delay = config.send_retry_delay if config else 2.0

            send_result = await self._send_with_backoff(
                contact, text, max_attempts, retry_delay,
            )

            if not send_result:
                logger.error(f"Failed to send message to {destination[:8]}...")
                return False

            logger.debug(f"Message sent to {destination[:8]}...: {text[:30]}...")
            return True

        except Exception as e:
            logger.error(f"Error sending message via BLE: {e}")
            return False

    async def _send_with_backoff(
        self, contact, text: str, max_attempts: int, retry_delay: float,
    ) -> bool:
        """Send message with retry and backoff between attempts."""
        for attempt in range(1, max_attempts + 1):
            try:
                send_result = await self._meshcore.commands.send_msg(contact, text)
                if send_result.type != EventType.ERROR:
                    return True
            except Exception as e:
                logger.warning(f"BLE send attempt {attempt}/{max_attempts} error: {e}")

            if attempt < max_attempts:
                delay = retry_delay * attempt
                logger.warning(
                    f"BLE send attempt {attempt}/{max_attempts} failed, "
                    f"retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        logger.error(f"All {max_attempts} BLE send attempts failed")
        return False

    async def send_advert(self, flood: bool = False) -> bool:
        """
        Send an advertisement announcing this node.

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
            if flood:
                await self._meshcore.commands.set_flood_scope("*")

            result = await self._meshcore.commands.send_appstart()

            if result.type == EventType.ERROR:
                logger.error(f"Failed to send advert: {result.payload}")
                return False

            flood_str = "flood" if flood else "zero-hop"
            logger.info(f"BLE Advertisement sent ({flood_str})")
            return True

        except Exception as e:
            logger.error(f"Error sending advert via BLE: {e}")
            return False

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
        """Handle incoming private message event from meshcore."""
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                recipient_key=self.identity.public_key if self.identity else None,
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
            )

            await self._message_queue.put(message)
            logger.debug(f"Received BLE private message from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing BLE private message: {e}")

    async def _on_channel_message(self, event: Any) -> None:
        """Handle incoming channel message event from meshcore (GRP_TXT)."""
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')
            channel_idx = data.get('channel_idx', 0)

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
                channel_idx=channel_idx,
                is_group_message=True,
            )

            await self._message_queue.put(message)
            logger.debug(f"Received BLE group message on channel {channel_idx} from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing BLE channel message: {e}")

    async def get_contacts(self) -> List[dict]:
        """Get list of known contacts from the device."""
        if self._mock is not None:
            return []

        if not self.connected or not self._meshcore:
            return []

        try:
            result = await self._meshcore.commands.get_contacts()
            if result.type != EventType.ERROR:
                return list(result.payload.values())
        except Exception as e:
            logger.error(f"Error getting contacts via BLE: {e}")

        return []

    async def get_battery(self) -> Optional[dict]:
        """Get battery status from the device."""
        if self._mock is not None:
            return {"level": 100, "charging": False}

        if not self.connected or not self._meshcore:
            return None

        try:
            result = await self._meshcore.commands.get_bat()
            if result.type != EventType.ERROR:
                return result.payload
        except Exception as e:
            logger.error(f"Error getting battery via BLE: {e}")

        return None

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
            if result.type != EventType.ERROR:
                logger.info("Device PIN set successfully")
                return True
            else:
                logger.error(f"Failed to set device PIN: {result.payload}")
                return False
        except Exception as e:
            logger.error(f"Error setting device PIN: {e}")
            return False

    @property
    def is_using_mock(self) -> bool:
        """Check if currently using mock implementation."""
        return self._mock is not None


class TCPMeshCoreConnection(BaseMeshCoreConnection):
    """
    MeshCore connection via TCP/IP.

    Connects to MeshCore companion radio devices over WiFi/Ethernet
    using TCP sockets. Useful for ESP32 nodes with WiFi capability.
    """

    def __init__(
        self,
        host: str = "192.168.1.100",
        port: int = 5000,
        timeout: float = 30.0,
        use_mock_fallback: bool = True,
        debug: bool = False,
    ):
        """
        Initialize TCP MeshCore connection.

        Args:
            host: IP address or hostname of the MeshCore device.
            port: TCP port number (default 4403).
            timeout: Connection timeout in seconds.
            use_mock_fallback: If True, fall back to mock when TCP unavailable.
            debug: Enable debug logging in meshcore library.
        """
        super().__init__()
        self.host = host
        self.port = port
        self.timeout = timeout
        self.debug = debug
        self._use_mock_fallback = use_mock_fallback

        # MeshCore instance
        self._meshcore: Optional[Any] = None
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._subscription = None
        self._channel_subscription = None
        self._auto_fetch_running = False

        # Fallback mock
        self._mock: Optional[MockMeshCoreConnection] = None

        # Resolve meshcore library (lazy load)

        # Check if meshcore is available
        if not MESHCORE_AVAILABLE:
            if use_mock_fallback:
                logger.warning(
                    "meshcore library not available for TCP. "
                    "Install with: pip install meshcore. "
                    "Using mock for development."
                )
                self._mock = MockMeshCoreConnection()
            else:
                raise ImportError(
                    "meshcore library is required for TCP. Install with: pip install meshcore"
                )

    async def connect(self) -> bool:
        """
        Connect to companion radio via TCP.

        Returns:
            True if connection successful
        """
        # If using mock fallback
        if self._mock is not None:
            result = await self._mock.connect()
            self.identity = self._mock.identity
            self.connected = self._mock.connected
            return result

        try:
            logger.info(f"Connecting to MeshCore device via TCP at {self.host}:{self.port}...")

            # Create TCP connection using meshcore_py
            self._meshcore = await MeshCore.create_tcp(
                self.host,
                self.port,
                debug=self.debug
            )

            # Get device identity from self_info
            if self._meshcore.self_info:
                self.identity = Identity(
                    public_key=self._meshcore.self_info.get('pubkey', '').hex()
                        if isinstance(self._meshcore.self_info.get('pubkey'), bytes)
                        else self._meshcore.self_info.get('pubkey', ''),
                    name=self._meshcore.self_info.get('name', 'Unknown'),
                    node_type=NodeType.ROOM,
                )
                logger.info(
                    f"Connected to MeshCore TCP device: {self.identity.name} "
                    f"({self.identity.short_key}...)"
                )
            else:
                # Create default identity
                self.identity = Identity(
                    public_key="0" * 64,
                    name="MeshBBS",
                    node_type=NodeType.ROOM,
                )
                logger.warning("Could not get device identity, using default")

            # Subscribe to incoming messages
            self._subscription = self._meshcore.subscribe(
                EventType.CONTACT_MSG_RECV,
                self._on_private_message
            )

            # Subscribe to channel messages
            self._channel_subscription = self._meshcore.subscribe(
                EventType.CHANNEL_MSG_RECV,
                self._on_channel_message
            )

            # Start auto-fetching messages
            await self._meshcore.start_auto_message_fetching()
            self._auto_fetch_running = True

            self.connected = True
            logger.info("MeshCore TCP connection established successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MeshCore TCP device: {e}")

            # Fall back to mock if enabled
            if self._use_mock_fallback and self._mock is None:
                logger.warning("Falling back to mock implementation")
                self._mock = MockMeshCoreConnection()
                result = await self._mock.connect()
                self.identity = self._mock.identity
                self.connected = self._mock.connected
                return result

            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from companion radio."""
        if self._mock is not None:
            await self._mock.disconnect()
            self.connected = False
            return

        if self._meshcore:
            try:
                # Stop auto-fetching
                if self._auto_fetch_running:
                    await self._meshcore.stop_auto_message_fetching()
                    self._auto_fetch_running = False

                # Unsubscribe from events
                if self._subscription:
                    self._meshcore.unsubscribe(self._subscription)
                    self._subscription = None

                if self._channel_subscription:
                    self._meshcore.unsubscribe(self._channel_subscription)
                    self._channel_subscription = None

                # Disconnect
                await self._meshcore.disconnect()
                logger.info("MeshCore TCP connection closed")

            except Exception as e:
                logger.error(f"Error during TCP disconnect: {e}")

            finally:
                self._meshcore = None

        self.connected = False

    async def send_message(
        self,
        destination: str,
        text: str,
        use_path: bool = True,
    ) -> bool:
        """
        Send a text message to a destination.

        Args:
            destination: Recipient's public key (hex string)
            text: Message text
            use_path: Whether to use known path (currently unused)

        Returns:
            True if message was sent successfully
        """
        if self._mock is not None:
            return await self._mock.send_message(destination, text, use_path)

        if not self.connected or not self._meshcore:
            logger.error("Cannot send: not connected")
            return False

        try:
            # Get contacts to find the destination
            result = await self._meshcore.commands.get_contacts()

            if result.type == EventType.ERROR:
                logger.error(f"Error getting contacts: {result.payload}")
                contact = destination
            else:
                # Find contact by public key prefix
                contact = self._meshcore.get_contact_by_key_prefix(destination[:12])
                if not contact:
                    contact = bytes.fromhex(destination) if len(destination) == 64 else destination

            # Send message with retry and backoff for reliability
            config = get_config() if get_config else None
            max_attempts = config.max_send_attempts if config else 2
            retry_delay = config.send_retry_delay if config else 2.0

            send_result = await self._send_with_backoff(
                contact, text, max_attempts, retry_delay,
            )

            if not send_result:
                logger.error(f"Failed to send message to {destination[:8]}...")
                return False

            logger.debug(f"Message sent to {destination[:8]}...: {text[:30]}...")
            return True

        except Exception as e:
            logger.error(f"Error sending message via TCP: {e}")
            return False

    async def _send_with_backoff(
        self, contact, text: str, max_attempts: int, retry_delay: float,
    ) -> bool:
        """Send message with retry and backoff between attempts."""
        for attempt in range(1, max_attempts + 1):
            try:
                send_result = await self._meshcore.commands.send_msg(contact, text)
                if send_result.type != EventType.ERROR:
                    return True
            except Exception as e:
                logger.warning(f"TCP send attempt {attempt}/{max_attempts} error: {e}")

            if attempt < max_attempts:
                delay = retry_delay * attempt
                logger.warning(
                    f"TCP send attempt {attempt}/{max_attempts} failed, "
                    f"retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        logger.error(f"All {max_attempts} TCP send attempts failed")
        return False

    async def send_advert(self, flood: bool = False) -> bool:
        """
        Send an advertisement announcing this node.

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
            if flood:
                await self._meshcore.commands.set_flood_scope("*")

            result = await self._meshcore.commands.send_appstart()

            if result.type == EventType.ERROR:
                logger.error(f"Failed to send advert: {result.payload}")
                return False

            flood_str = "flood" if flood else "zero-hop"
            logger.info(f"TCP Advertisement sent ({flood_str})")
            return True

        except Exception as e:
            logger.error(f"Error sending advert via TCP: {e}")
            return False

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
        """Handle incoming private message event from meshcore."""
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                recipient_key=self.identity.public_key if self.identity else None,
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
            )

            await self._message_queue.put(message)
            logger.debug(f"Received TCP private message from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing TCP private message: {e}")

    async def _on_channel_message(self, event: Any) -> None:
        """Handle incoming channel message event from meshcore (GRP_TXT)."""
        try:
            data = event.payload

            sender_key = data.get('pubkey_prefix', '')
            if isinstance(sender_key, bytes):
                sender_key = sender_key.hex()

            text = data.get('text', '')
            channel_idx = data.get('channel_idx', 0)

            message = Message(
                sender_key=sender_key,
                text=text,
                timestamp=datetime.utcnow(),
                hops=data.get('hops', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr'),
                channel_idx=channel_idx,
                is_group_message=True,
            )

            await self._message_queue.put(message)
            logger.debug(f"Received TCP group message on channel {channel_idx} from {sender_key[:8]}...")

        except Exception as e:
            logger.error(f"Error processing TCP channel message: {e}")

    async def get_contacts(self) -> List[dict]:
        """Get list of known contacts from the device."""
        if self._mock is not None:
            return []

        if not self.connected or not self._meshcore:
            return []

        try:
            result = await self._meshcore.commands.get_contacts()
            if result.type != EventType.ERROR:
                return list(result.payload.values())
        except Exception as e:
            logger.error(f"Error getting contacts via TCP: {e}")

        return []

    async def get_battery(self) -> Optional[dict]:
        """Get battery status from the device."""
        if self._mock is not None:
            return {"level": 100, "charging": False}

        if not self.connected or not self._meshcore:
            return None

        try:
            result = await self._meshcore.commands.get_bat()
            if result.type != EventType.ERROR:
                return result.payload
        except Exception as e:
            logger.error(f"Error getting battery via TCP: {e}")

        return None

    @property
    def is_using_mock(self) -> bool:
        """Check if currently using mock implementation."""
        return self._mock is not None

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
        self._message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._sent_messages: List[Message] = []

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
        await self._message_queue.put(message)
        logger.debug(f"Injected message from {sender_key[:8]}: {text[:30]}...")

    def get_sent_messages(self) -> List[Message]:
        """Get all messages sent through this mock connection."""
        return self._sent_messages.copy()

    def clear_sent_messages(self) -> None:
        """Clear the sent messages list."""
        self._sent_messages.clear()
