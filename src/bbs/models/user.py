"""
User model for MeshCore BBS.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Index
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    """
    Represents a user in the BBS system.

    Users are identified by their MeshCore public key, not by traditional
    username/password. The public key is the primary identifier.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    public_key = Column(String(64), unique=True, nullable=False, index=True)
    nickname = Column(String(32), nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Roles and permissions
    is_admin = Column(Boolean, default=False, nullable=False)
    is_moderator = Column(Boolean, default=False, nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    ban_reason = Column(String(255), nullable=True)
    banned_at = Column(DateTime, nullable=True)
    is_muted = Column(Boolean, default=False, nullable=False)
    mute_reason = Column(String(255), nullable=True)
    muted_at = Column(DateTime, nullable=True)
    kicked_until = Column(DateTime, nullable=True)
    kick_reason = Column(String(255), nullable=True)

    # Relationships
    messages = relationship("Message", back_populates="author", lazy="dynamic")

    # Indexes
    __table_args__ = (Index("idx_users_last_seen", "last_seen"),)

    def __repr__(self) -> str:
        return f"<User {self.display_name} ({self.public_key[:8]}...)>"

    @property
    def display_name(self) -> str:
        """Get display name (nickname or truncated public key)."""
        if self.nickname:
            return self.nickname
        return self.public_key[:8]

    @property
    def short_key(self) -> str:
        """Get shortened public key for display."""
        return self.public_key[:8]

    def is_active(self) -> bool:
        """Check if user is active (not banned and not kicked)."""
        return not self.is_banned and not self.is_kicked

    @property
    def is_kicked(self) -> bool:
        """Check if user is currently kicked."""
        if self.kicked_until is None:
            return False
        return datetime.utcnow() < self.kicked_until

    def can_post(self) -> bool:
        """Check if user can post messages."""
        return self.is_active() and not self.is_muted

    def can_moderate(self) -> bool:
        """Check if user has moderation privileges."""
        return self.is_admin or self.is_moderator

    def ban(self, reason: Optional[str] = None) -> None:
        """Ban this user."""
        self.is_banned = True
        self.ban_reason = reason
        self.banned_at = datetime.utcnow()

    def unban(self) -> None:
        """Remove ban from this user."""
        self.is_banned = False
        self.ban_reason = None
        self.banned_at = None

    def mute(self, reason: Optional[str] = None) -> None:
        """Mute this user (can read but not post)."""
        self.is_muted = True
        self.mute_reason = reason
        self.muted_at = datetime.utcnow()

    def unmute(self) -> None:
        """Remove mute from this user."""
        self.is_muted = False
        self.mute_reason = None
        self.muted_at = None

    def kick(self, minutes: int, reason: Optional[str] = None) -> None:
        """Kick this user for a specified duration."""
        self.kicked_until = datetime.utcnow() + timedelta(minutes=minutes)
        self.kick_reason = reason

    def unkick(self) -> None:
        """Remove kick from this user."""
        self.kicked_until = None
        self.kick_reason = None

    @property
    def kick_remaining_minutes(self) -> int:
        """Get remaining kick time in minutes."""
        if not self.is_kicked:
            return 0
        remaining = self.kicked_until - datetime.utcnow()
        return max(0, int(remaining.total_seconds() / 60))

    def promote_to_moderator(self) -> None:
        """Promote this user to moderator."""
        self.is_moderator = True

    def demote_from_moderator(self) -> None:
        """Remove moderator status from this user."""
        self.is_moderator = False

    def promote_to_admin(self) -> None:
        """Promote this user to admin."""
        self.is_admin = True
        self.is_moderator = True  # Admins are also moderators

    def demote_from_admin(self) -> None:
        """Remove admin status from this user (keeps moderator)."""
        self.is_admin = False

    @property
    def role_display(self) -> str:
        """Get display string for user's role."""
        if self.is_admin:
            return "Admin"
        elif self.is_moderator:
            return "Moderatore"
        else:
            return "Utente"

    def update_last_seen(self) -> None:
        """Update the last seen timestamp."""
        self.last_seen = datetime.utcnow()
