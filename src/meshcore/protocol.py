"""
MeshCore protocol definitions and packet handling.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


class PacketType(IntEnum):
    """MeshCore packet types as defined in Packet.h"""

    REQ = 0x00  # Request
    RESPONSE = 0x01  # Response to REQ or ANON_REQ
    TXT_MSG = 0x02  # Plain text message
    ACK = 0x03  # Simple acknowledgment
    ADVERT = 0x04  # Node advertising its identity
    GRP_TXT = 0x05  # Group text message
    GRP_DATA = 0x06  # Group datagram
    ANON_REQ = 0x07  # Anonymous request
    PATH = 0x08  # Path information


class NodeType(IntEnum):
    """MeshCore node types for contact/advert."""

    CHAT = 1
    REPEATER = 2
    ROOM = 3
    SENSOR = 4


@dataclass
class PacketInfo:
    """
    Information about a received packet.

    Contains metadata from the MeshCore network.
    """

    packet_type: PacketType
    hops: int = 0
    rssi: Optional[int] = None
    snr: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    @property
    def type_name(self) -> str:
        """Get human-readable packet type name."""
        return PacketType(self.packet_type).name


def format_public_key(key: str, length: int = 8) -> str:
    """
    Format a public key for display.

    Args:
        key: Full public key (hex string)
        length: Number of characters to show

    Returns:
        Truncated key with ellipsis
    """
    if len(key) <= length:
        return key
    return key[:length] + "..."


def validate_public_key(key: str) -> bool:
    """
    Validate a public key format.

    Args:
        key: Public key to validate

    Returns:
        True if valid hex string of correct length
    """
    if not key:
        return False

    # MeshCore uses 32-byte (64 hex chars) public keys
    if len(key) != 64:
        return False

    try:
        int(key, 16)
        return True
    except ValueError:
        return False
