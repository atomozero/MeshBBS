"""
Mention notification system for MeshCore BBS.

Detects @nickname mentions in messages and creates notifications.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import re
import logging
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("meshbbs.mentions")

# Regex to detect @mentions
# Matches @nickname where nickname is 2-20 alphanumeric chars
MENTION_PATTERN = re.compile(r"@([a-zA-Z][a-zA-Z0-9_]{1,19})\b")


@dataclass
class Mention:
    """Represents a mention notification."""

    recipient_key: str
    sender_key: str
    sender_name: str
    message_id: int
    area_name: str
    excerpt: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MentionNotifier:
    """
    Handles @nickname mention detection and notifications.

    Mentions are stored in memory and cleared when the user checks them.
    """

    # Maximum mentions per user to prevent memory issues
    MAX_MENTIONS_PER_USER = 50

    def __init__(self):
        # Store mentions by recipient public key
        self._mentions: Dict[str, List[Mention]] = defaultdict(list)

    def extract_mentions(self, text: str) -> Set[str]:
        """
        Extract all @mentions from text.

        Args:
            text: Message text to scan

        Returns:
            Set of mentioned nicknames (lowercase)
        """
        matches = MENTION_PATTERN.findall(text)
        return {m.lower() for m in matches}

    def create_mention(
        self,
        recipient_key: str,
        sender_key: str,
        sender_name: str,
        message_id: int,
        area_name: str,
        message_body: str,
    ) -> None:
        """
        Create a mention notification.

        Args:
            recipient_key: Public key of mentioned user
            sender_key: Public key of sender
            sender_name: Display name of sender
            message_id: ID of the message with mention
            area_name: Name of the area where message was posted
            message_body: Full message body (will be truncated for excerpt)
        """
        # Create excerpt (first 50 chars)
        excerpt = message_body[:50]
        if len(message_body) > 50:
            excerpt += "..."

        mention = Mention(
            recipient_key=recipient_key,
            sender_key=sender_key,
            sender_name=sender_name,
            message_id=message_id,
            area_name=area_name,
            excerpt=excerpt,
        )

        # Add to user's mentions
        mentions_list = self._mentions[recipient_key]
        mentions_list.append(mention)

        # Trim if over limit (keep most recent)
        if len(mentions_list) > self.MAX_MENTIONS_PER_USER:
            self._mentions[recipient_key] = mentions_list[-self.MAX_MENTIONS_PER_USER :]

        logger.debug(
            f"Created mention for {recipient_key[:8]} from {sender_name} in #{area_name}"
        )

    def get_mentions(self, user_key: str, clear: bool = True) -> List[Mention]:
        """
        Get pending mentions for a user.

        Args:
            user_key: User's public key
            clear: Whether to clear mentions after retrieving (default True)

        Returns:
            List of Mention objects
        """
        mentions = list(self._mentions.get(user_key, []))

        if clear and user_key in self._mentions:
            del self._mentions[user_key]

        return mentions

    def get_mention_count(self, user_key: str) -> int:
        """Get count of pending mentions for a user."""
        return len(self._mentions.get(user_key, []))

    def has_mentions(self, user_key: str) -> bool:
        """Check if user has pending mentions."""
        return user_key in self._mentions and len(self._mentions[user_key]) > 0

    def clear_mentions(self, user_key: str) -> int:
        """
        Clear all mentions for a user.

        Returns:
            Number of mentions cleared
        """
        count = len(self._mentions.get(user_key, []))
        if user_key in self._mentions:
            del self._mentions[user_key]
        return count

    def get_stats(self) -> dict:
        """Get mention system statistics."""
        total_mentions = sum(len(m) for m in self._mentions.values())
        return {
            "users_with_mentions": len(self._mentions),
            "total_pending_mentions": total_mentions,
        }


# Global instance for the application
_mention_notifier: Optional[MentionNotifier] = None


def get_mention_notifier() -> MentionNotifier:
    """Get or create the global mention notifier instance."""
    global _mention_notifier
    if _mention_notifier is None:
        _mention_notifier = MentionNotifier()
    return _mention_notifier


def process_mentions_in_message(
    session,
    message_body: str,
    sender_key: str,
    sender_name: str,
    message_id: int,
    area_name: str,
) -> List[str]:
    """
    Process a message for @mentions and create notifications.

    Args:
        session: Database session
        message_body: The message text
        sender_key: Sender's public key
        sender_name: Sender's display name
        message_id: ID of the posted message
        area_name: Name of the area

    Returns:
        List of nicknames that were notified
    """
    from bbs.repositories.user_repository import UserRepository

    notifier = get_mention_notifier()
    user_repo = UserRepository(session)

    # Extract mentions from message
    mentioned_nicknames = notifier.extract_mentions(message_body)

    if not mentioned_nicknames:
        return []

    notified = []

    for nickname in mentioned_nicknames:
        # Find user by nickname
        user = user_repo.get_by_nickname(nickname)

        if user is None:
            continue

        # Don't notify yourself
        if user.public_key == sender_key:
            continue

        # Don't notify banned users
        if user.is_banned:
            continue

        # Create the mention notification
        notifier.create_mention(
            recipient_key=user.public_key,
            sender_key=sender_key,
            sender_name=sender_name,
            message_id=message_id,
            area_name=area_name,
            message_body=message_body,
        )

        notified.append(user.nickname or nickname)
        logger.info(f"Mention notification created for @{nickname}")

    return notified


def format_mentions_for_inbox(mentions: List[Mention]) -> str:
    """
    Format mentions for display in inbox.

    Args:
        mentions: List of Mention objects

    Returns:
        Formatted string for display
    """
    if not mentions:
        return ""

    lines = [f"\n--- Menzioni ({len(mentions)}) ---"]

    for m in mentions:
        lines.append(f"@{m.sender_name} in #{m.area_name}: \"{m.excerpt}\"")
        lines.append(f"  -> /read {m.message_id}")

    lines.append("(Le menzioni scompaiono dopo la lettura)")

    return "\n".join(lines)
