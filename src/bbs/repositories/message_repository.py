"""
Message repository for data access operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload

from .base_repository import BaseRepository
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType


class MessageRepository(BaseRepository[Message]):
    """Repository for Message entity operations."""

    model = Message

    def __init__(self, session: Session):
        super().__init__(session)

    def get_recent_messages(
        self,
        area_name: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Message]:
        """
        Get recent messages from an area.

        Args:
            area_name: Name of the area
            limit: Maximum messages to return
            offset: Number of messages to skip

        Returns:
            List of messages, most recent first
        """
        return (
            self.session.query(Message)
            .join(Area)
            .filter(Area.name.ilike(area_name))
            .options(joinedload(Message.author))
            .order_by(Message.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_message_with_author(self, message_id: int) -> Optional[Message]:
        """
        Get a message with its author preloaded.

        Args:
            message_id: Message ID

        Returns:
            Message with author or None
        """
        return (
            self.session.query(Message)
            .options(joinedload(Message.author))
            .options(joinedload(Message.area))
            .filter(Message.id == message_id)
            .first()
        )

    def create_message(
        self,
        area_name: str,
        sender_key: str,
        body: str,
        subject: Optional[str] = None,
        parent_id: Optional[int] = None,
        hops: int = 0,
        rssi: Optional[int] = None,
    ) -> Optional[Message]:
        """
        Create a new message in an area.

        Args:
            area_name: Name of the area
            sender_key: Sender's public key
            body: Message body
            subject: Optional subject
            parent_id: Parent message ID for replies
            hops: Number of hops from MeshCore
            rssi: Signal strength

        Returns:
            Created message or None if area not found
        """
        # Get area
        area = (
            self.session.query(Area)
            .filter(Area.name.ilike(area_name))
            .first()
        )

        if not area:
            return None

        # Create message
        message = Message(
            area_id=area.id,
            sender_key=sender_key,
            body=body,
            subject=subject,
            parent_id=parent_id,
            hops=hops,
            rssi=rssi,
            timestamp=datetime.utcnow(),
        )

        self.session.add(message)

        # Update area statistics
        area.increment_message_count()

        # Log activity
        self.session.add(
            ActivityLog.log(
                EventType.MESSAGE_POSTED,
                user_key=sender_key,
                details=f"Message #{message.id} in {area_name}",
            )
        )

        return message

    def get_thread(self, message_id: int) -> List[Message]:
        """
        Get all messages in a thread.

        Args:
            message_id: ID of any message in the thread

        Returns:
            List of messages in chronological order
        """
        message = self.get_message_with_author(message_id)
        if not message:
            return []

        return message.get_thread()

    def get_user_messages(
        self,
        public_key: str,
        limit: int = 10,
    ) -> List[Message]:
        """
        Get recent messages by a user.

        Args:
            public_key: User's public key
            limit: Maximum messages to return

        Returns:
            List of messages
        """
        return (
            self.session.query(Message)
            .filter(Message.sender_key == public_key)
            .options(joinedload(Message.area))
            .order_by(Message.timestamp.desc())
            .limit(limit)
            .all()
        )

    def search_messages(
        self,
        query: str,
        area_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[Message]:
        """
        Search messages by content.

        Args:
            query: Search query
            area_name: Optional area to search in
            limit: Maximum results

        Returns:
            List of matching messages
        """
        q = self.session.query(Message).filter(
            Message.body.ilike(f"%{query}%")
        )

        if area_name:
            q = q.join(Area).filter(Area.name.ilike(area_name))

        return (
            q.options(joinedload(Message.author))
            .order_by(Message.timestamp.desc())
            .limit(limit)
            .all()
        )

    def count_by_area(self, area_name: str) -> int:
        """
        Count messages in an area.

        Args:
            area_name: Area name

        Returns:
            Message count
        """
        return (
            self.session.query(Message)
            .join(Area)
            .filter(Area.name.ilike(area_name))
            .count()
        )
