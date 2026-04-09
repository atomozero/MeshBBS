"""
Area (forum/board) model for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship

from .base import Base

if TYPE_CHECKING:
    from .message import Message


class Area(Base):
    """
    Represents a discussion area (forum/board) in the BBS.

    Areas are thematic sections where users can post messages.
    Similar to newsgroups or forum boards.
    """

    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(32), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    is_readonly = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Statistics (updated by triggers or manually)
    message_count = Column(Integer, default=0, nullable=False)
    last_post_at = Column(DateTime, nullable=True)

    # Relationships
    messages = relationship(
        "Message",
        back_populates="area",
        lazy="dynamic",
        order_by="Message.timestamp.desc()",
    )

    def __repr__(self) -> str:
        return f"<Area {self.name}>"

    def get_recent_messages(self, limit: int = 10) -> List["Message"]:
        """
        Get the most recent messages in this area.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of Message objects, most recent first
        """
        return self.messages.limit(limit).all()

    def increment_message_count(self) -> None:
        """Increment the message counter and update last post time."""
        self.message_count += 1
        self.last_post_at = datetime.utcnow()

    def can_post(self) -> bool:
        """Check if posting is allowed in this area."""
        return self.is_public and not self.is_readonly
