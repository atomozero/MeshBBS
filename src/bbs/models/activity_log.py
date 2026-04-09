"""
Activity log model for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Index

from .base import Base


class EventType(str, Enum):
    """Types of events that can be logged."""

    # User events
    USER_FIRST_SEEN = "user_first_seen"
    USER_NICKNAME_SET = "user_nickname_set"
    USER_BANNED = "user_banned"
    USER_UNBANNED = "user_unbanned"
    USER_MUTED = "user_muted"
    USER_UNMUTED = "user_unmuted"
    USER_PROMOTED = "user_promoted"
    USER_DEMOTED = "user_demoted"
    USER_KICKED = "user_kicked"
    USER_UNKICKED = "user_unkicked"

    # Message events
    MESSAGE_POSTED = "message_posted"
    MESSAGE_DELETED = "message_deleted"
    PRIVATE_MSG_SENT = "private_msg_sent"

    # Area events
    AREA_CREATED = "area_created"
    AREA_DELETED = "area_deleted"
    AREA_MODIFIED = "area_modified"

    # System events
    BBS_STARTED = "bbs_started"
    BBS_STOPPED = "bbs_stopped"
    ADVERT_SENT = "advert_sent"
    ERROR = "error"


class ActivityLog(Base):
    """
    Logs system and user activity for auditing and debugging.

    Implements retention policy - old logs should be periodically cleaned.
    """

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    user_key = Column(String(64), nullable=True, index=True)
    details = Column(Text, nullable=True)

    # Indexes
    __table_args__ = (Index("idx_activity_type_time", "event_type", "timestamp"),)

    def __repr__(self) -> str:
        return f"<ActivityLog {self.event_type} at {self.timestamp}>"

    @classmethod
    def log(
        cls,
        event_type: EventType,
        user_key: Optional[str] = None,
        details: Optional[str] = None,
    ) -> "ActivityLog":
        """
        Create a new activity log entry.

        Args:
            event_type: Type of event
            user_key: Public key of user involved (if any)
            details: Additional details about the event

        Returns:
            ActivityLog instance (not yet added to session)
        """
        return cls(
            event_type=event_type.value,
            user_key=user_key,
            details=details,
        )


def log_activity(
    session,
    event_type: EventType,
    user_key: Optional[str] = None,
    details: Optional[str] = None,
) -> ActivityLog:
    """
    Helper function to log an activity.

    Args:
        session: SQLAlchemy session
        event_type: Type of event
        user_key: Public key of user involved
        details: Additional details

    Returns:
        Created ActivityLog entry
    """
    entry = ActivityLog.log(event_type, user_key, details)
    session.add(entry)
    return entry
