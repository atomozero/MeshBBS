"""
Private message repository for data access operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from .base_repository import BaseRepository
from bbs.models.private_message import PrivateMessage
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType


class PrivateMessageRepository(BaseRepository[PrivateMessage]):
    """Repository for PrivateMessage entity operations."""

    model = PrivateMessage

    def __init__(self, session: Session):
        super().__init__(session)

    def send_message(
        self,
        sender_key: str,
        recipient_key: str,
        body: str,
    ) -> Optional[PrivateMessage]:
        """
        Send a private message.

        Args:
            sender_key: Sender's public key
            recipient_key: Recipient's public key
            body: Message body

        Returns:
            Created PrivateMessage or None if recipient doesn't exist
        """
        # Verify recipient exists
        recipient = (
            self.session.query(User)
            .filter(User.public_key == recipient_key)
            .first()
        )
        if not recipient:
            return None

        # Create message
        message = PrivateMessage(
            sender_key=sender_key,
            recipient_key=recipient_key,
            body=body,
            timestamp=datetime.utcnow(),
        )
        self.session.add(message)

        # Log activity
        self.session.add(
            ActivityLog.log(
                EventType.PRIVATE_MSG_SENT,
                user_key=sender_key,
                details=f"To: {recipient_key[:8]}...",
            )
        )

        return message

    def get_inbox(
        self,
        user_key: str,
        limit: int = 10,
        offset: int = 0,
        unread_only: bool = False,
    ) -> List[PrivateMessage]:
        """
        Get inbox messages for a user.

        Args:
            user_key: User's public key
            limit: Maximum messages to return
            offset: Offset for pagination
            unread_only: If True, only return unread messages

        Returns:
            List of private messages
        """
        query = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.recipient_key == user_key)
        )

        if unread_only:
            query = query.filter(PrivateMessage.is_read == False)

        return (
            query
            .order_by(PrivateMessage.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_sent(
        self,
        user_key: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[PrivateMessage]:
        """
        Get sent messages for a user.

        Args:
            user_key: User's public key
            limit: Maximum messages to return
            offset: Offset for pagination

        Returns:
            List of sent private messages
        """
        return (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.sender_key == user_key)
            .order_by(PrivateMessage.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_conversation(
        self,
        user1_key: str,
        user2_key: str,
        limit: int = 20,
    ) -> List[PrivateMessage]:
        """
        Get conversation between two users.

        Args:
            user1_key: First user's public key
            user2_key: Second user's public key
            limit: Maximum messages to return

        Returns:
            List of messages between the two users, ordered by time
        """
        return (
            self.session.query(PrivateMessage)
            .filter(
                or_(
                    and_(
                        PrivateMessage.sender_key == user1_key,
                        PrivateMessage.recipient_key == user2_key,
                    ),
                    and_(
                        PrivateMessage.sender_key == user2_key,
                        PrivateMessage.recipient_key == user1_key,
                    ),
                )
            )
            .order_by(PrivateMessage.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_unread_count(self, user_key: str) -> int:
        """
        Get count of unread messages for a user.

        Args:
            user_key: User's public key

        Returns:
            Number of unread messages
        """
        return (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.recipient_key == user_key)
            .filter(PrivateMessage.is_read == False)
            .count()
        )

    def mark_as_read(self, message_id: int, user_key: str) -> Optional[PrivateMessage]:
        """
        Mark a message as read.

        Only the recipient can mark a message as read.

        Args:
            message_id: Message ID
            user_key: User's public key (must be recipient)

        Returns:
            Updated message or None if not found/not authorized
        """
        message = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.id == message_id)
            .filter(PrivateMessage.recipient_key == user_key)
            .first()
        )

        if message:
            message.mark_as_read()

        return message

    def mark_conversation_as_read(self, user_key: str, other_key: str) -> int:
        """
        Mark all messages from another user as read.

        Args:
            user_key: Recipient's public key
            other_key: Sender's public key

        Returns:
            Number of messages marked as read
        """
        messages = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.recipient_key == user_key)
            .filter(PrivateMessage.sender_key == other_key)
            .filter(PrivateMessage.is_read == False)
            .all()
        )

        count = 0
        for msg in messages:
            msg.mark_as_read()
            count += 1

        return count

    def get_message_for_user(
        self,
        message_id: int,
        user_key: str,
    ) -> Optional[PrivateMessage]:
        """
        Get a message if the user is sender or recipient.

        Args:
            message_id: Message ID
            user_key: User's public key

        Returns:
            Message or None if not found/not authorized
        """
        return (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.id == message_id)
            .filter(
                or_(
                    PrivateMessage.sender_key == user_key,
                    PrivateMessage.recipient_key == user_key,
                )
            )
            .first()
        )

    def delete_message(self, message_id: int, user_key: str) -> bool:
        """
        Delete a message (only sender can delete).

        Args:
            message_id: Message ID
            user_key: User's public key (must be sender)

        Returns:
            True if deleted, False otherwise
        """
        message = (
            self.session.query(PrivateMessage)
            .filter(PrivateMessage.id == message_id)
            .filter(PrivateMessage.sender_key == user_key)
            .first()
        )

        if message:
            self.session.delete(message)
            return True

        return False
