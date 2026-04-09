"""
Private message model for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class PrivateMessage(Base):
    """
    Represents a private message between two users.

    Private messages are direct communications not visible in public areas.
    """

    __tablename__ = "private_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_key = Column(String(64), ForeignKey("users.public_key"), nullable=False)
    recipient_key = Column(String(64), ForeignKey("users.public_key"), nullable=False)
    body = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Read status
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)

    # Relationships
    sender = relationship("User", foreign_keys=[sender_key])
    recipient = relationship("User", foreign_keys=[recipient_key])

    # Indexes
    __table_args__ = (
        Index("idx_pm_recipient_read", "recipient_key", "is_read"),
        Index("idx_pm_sender", "sender_key"),
    )

    def __repr__(self) -> str:
        status = "read" if self.is_read else "unread"
        return f"<PM #{self.id} {self.sender_key[:8]} -> {self.recipient_key[:8]} ({status})>"

    @property
    def preview(self) -> str:
        """Get a preview of the message body (max 30 chars)."""
        if len(self.body) <= 30:
            return self.body
        return self.body[:27] + "..."

    @property
    def age_string(self) -> str:
        """Get human-readable age of the message."""
        delta = datetime.utcnow() - self.timestamp

        if delta.days > 0:
            return f"{delta.days}g"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m"
        else:
            return "ora"

    def mark_as_read(self) -> None:
        """Mark this message as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
