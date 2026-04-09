"""
Message model for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User
    from .area import Area


class Message(Base):
    """
    Represents a public message in an area.

    Messages can be part of threads (parent_id for replies).
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    area_id = Column(Integer, ForeignKey("areas.id"), nullable=False)
    sender_key = Column(String(64), ForeignKey("users.public_key"), nullable=False)
    subject = Column(String(64), nullable=True)
    body = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Threading support
    parent_id = Column(Integer, ForeignKey("messages.id"), nullable=True)

    # Metadata from MeshCore
    hops = Column(Integer, default=0)
    rssi = Column(Integer, nullable=True)
    snr = Column(Integer, nullable=True)

    # Relationships
    area = relationship("Area", back_populates="messages")
    author = relationship("User", back_populates="messages", foreign_keys=[sender_key])
    parent = relationship("Message", remote_side=[id], backref="replies")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_messages_area_timestamp", "area_id", "timestamp"),
        Index("idx_messages_sender", "sender_key"),
        Index("idx_messages_parent", "parent_id"),
    )

    def __repr__(self) -> str:
        preview = self.body[:20] + "..." if len(self.body) > 20 else self.body
        return f"<Message #{self.id} by {self.sender_key[:8]}: {preview}>"

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

    def get_thread(self) -> List["Message"]:
        """
        Get all messages in this thread (including self).

        Returns:
            List of messages in chronological order
        """
        # Find root message
        root = self
        while root.parent is not None:
            root = root.parent

        # Collect all replies recursively
        def collect_replies(msg: "Message") -> List["Message"]:
            result = [msg]
            for reply in sorted(msg.replies, key=lambda m: m.timestamp):
                result.extend(collect_replies(reply))
            return result

        return collect_replies(root)

    @property
    def is_reply(self) -> bool:
        """Check if this message is a reply to another."""
        return self.parent_id is not None

    @property
    def reply_count(self) -> int:
        """Get the number of direct replies to this message."""
        return len(self.replies) if self.replies else 0
