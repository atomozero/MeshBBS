"""
Message delivery status tracking for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import relationship

from .base import Base


class DeliveryState(str, Enum):
    """Possible states for message delivery."""

    PENDING = "pending"      # Message queued for sending
    SENDING = "sending"      # Message being transmitted
    SENT = "sent"            # Message sent, awaiting ACK
    DELIVERED = "delivered"  # ACK received from recipient
    READ = "read"            # Recipient has read the message
    FAILED = "failed"        # Delivery failed after retries


class DeliveryStatus(Base):
    """
    Tracks delivery status of outgoing messages.

    Records the delivery state and timestamps for messages sent
    through the MeshCore network.
    """

    __tablename__ = "delivery_statuses"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Message identification
    message_type = Column(String(20), nullable=False)  # 'private', 'public', 'broadcast'
    message_id = Column(Integer, nullable=False)  # Reference to the message
    external_id = Column(String(32), nullable=True)  # MeshCore message ID

    # Parties involved
    sender_key = Column(String(64), nullable=False)
    recipient_key = Column(String(64), nullable=True)  # Null for broadcasts

    # Delivery state
    state = Column(SQLEnum(DeliveryState), default=DeliveryState.PENDING, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Retry tracking
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    # Error info
    error_message = Column(String(255), nullable=True)

    # Network info from ACK
    ack_hops = Column(Integer, nullable=True)
    ack_rssi = Column(Integer, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_delivery_message", "message_type", "message_id"),
        Index("idx_delivery_external", "external_id"),
        Index("idx_delivery_state", "state"),
        Index("idx_delivery_sender", "sender_key"),
        Index("idx_delivery_recipient", "recipient_key"),
    )

    def __repr__(self) -> str:
        return f"<DeliveryStatus #{self.id} {self.message_type}:{self.message_id} -> {self.state.value}>"

    def mark_sending(self) -> None:
        """Mark message as being sent."""
        self.state = DeliveryState.SENDING

    def mark_sent(self, external_id: Optional[str] = None) -> None:
        """Mark message as sent."""
        self.state = DeliveryState.SENT
        self.sent_at = datetime.utcnow()
        if external_id:
            self.external_id = external_id

    def mark_delivered(self, hops: Optional[int] = None, rssi: Optional[int] = None) -> None:
        """Mark message as delivered (ACK received)."""
        self.state = DeliveryState.DELIVERED
        self.delivered_at = datetime.utcnow()
        if hops is not None:
            self.ack_hops = hops
        if rssi is not None:
            self.ack_rssi = rssi

    def mark_read(self) -> None:
        """Mark message as read by recipient."""
        self.state = DeliveryState.READ
        self.read_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark message delivery as failed."""
        self.state = DeliveryState.FAILED
        self.failed_at = datetime.utcnow()
        self.error_message = error

    def increment_retry(self) -> bool:
        """
        Increment retry counter.

        Returns:
            True if more retries are available, False otherwise
        """
        self.retry_count += 1
        return self.retry_count < self.max_retries

    @property
    def is_pending(self) -> bool:
        """Check if message is pending delivery."""
        return self.state == DeliveryState.PENDING

    @property
    def is_delivered(self) -> bool:
        """Check if message was delivered."""
        return self.state in (DeliveryState.DELIVERED, DeliveryState.READ)

    @property
    def is_failed(self) -> bool:
        """Check if delivery failed."""
        return self.state == DeliveryState.FAILED

    @property
    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.state == DeliveryState.FAILED and self.retry_count < self.max_retries

    @property
    def delivery_time_ms(self) -> Optional[int]:
        """
        Get delivery time in milliseconds.

        Returns:
            Time from sent to delivered in ms, or None if not delivered
        """
        if self.sent_at and self.delivered_at:
            delta = self.delivered_at - self.sent_at
            return int(delta.total_seconds() * 1000)
        return None
