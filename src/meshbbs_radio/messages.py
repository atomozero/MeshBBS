"""
Message types for MeshCore communication.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from .protocol import PacketType, NodeType, PacketInfo


@dataclass
class Message:
    """
    Represents an incoming or outgoing MeshCore text message.

    This is the primary message type for BBS communication.
    """

    sender_key: str
    text: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recipient_key: Optional[str] = None
    message_id: Optional[str] = None

    # Network metadata
    hops: int = 0
    rssi: Optional[int] = None
    snr: Optional[float] = None

    # Routing info
    path: List[str] = field(default_factory=list)
    is_flood: bool = True

    # Group/Channel info (for GRP_TXT messages)
    channel_idx: Optional[int] = None
    is_group_message: bool = False

    @property
    def is_direct(self) -> bool:
        """Check if this is a direct (non-broadcast) message."""
        return self.recipient_key is not None and not self.is_group_message

    @property
    def is_channel(self) -> bool:
        """Check if this is a channel/group message."""
        return self.is_group_message or self.channel_idx is not None

    @property
    def sender_short(self) -> str:
        """Get shortened sender key for display."""
        return self.sender_key[:8] if self.sender_key else "unknown"

    def __str__(self) -> str:
        if self.is_channel:
            return f"[CH{self.channel_idx}] from {self.sender_short}: {self.text[:30]}..."
        return f"Message from {self.sender_short}: {self.text[:30]}..."


@dataclass
class GroupMessage:
    """
    Represents a MeshCore group/channel text message (GRP_TXT).

    Group messages are broadcast to all nodes subscribed to a specific channel.
    """

    sender_key: str
    text: str
    channel_idx: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: Optional[str] = None

    # Network metadata
    hops: int = 0
    rssi: Optional[int] = None
    snr: Optional[float] = None

    @property
    def sender_short(self) -> str:
        """Get shortened sender key for display."""
        return self.sender_key[:8] if self.sender_key else "unknown"

    def to_message(self) -> Message:
        """Convert to a generic Message for processing."""
        return Message(
            sender_key=self.sender_key,
            text=self.text,
            timestamp=self.timestamp,
            message_id=self.message_id,
            hops=self.hops,
            rssi=self.rssi,
            snr=self.snr,
            channel_idx=self.channel_idx,
            is_group_message=True,
        )

    def __str__(self) -> str:
        return f"[CH{self.channel_idx}] from {self.sender_short}: {self.text[:30]}..."


@dataclass
class Advert:
    """
    Represents a node advertisement.

    Adverts announce a node's presence on the network.
    """

    public_key: str
    name: str
    node_type: NodeType = NodeType.CHAT
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Optional location
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Network metadata
    hops: int = 0
    rssi: Optional[int] = None

    @property
    def has_location(self) -> bool:
        """Check if advert includes location."""
        return self.latitude is not None and self.longitude is not None

    @property
    def type_name(self) -> str:
        """Get human-readable node type."""
        return NodeType(self.node_type).name.lower()

    def __str__(self) -> str:
        return f"Advert: {self.name} ({self.type_name})"


@dataclass
class Ack:
    """
    Represents an acknowledgment for a sent message.

    ACKs confirm that a message was received by the destination.
    """

    message_id: str
    sender_key: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Path learned from this ACK
    path: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"ACK for {self.message_id} from {self.sender_key[:8]}"
