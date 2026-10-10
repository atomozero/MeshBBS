"""
Per-user preferences and deferred notifications.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from .base import Base


class UserPrefs(Base):
    """
    User preferences (one row per user, created on first change).

    A missing row means "all defaults" (notifications enabled).
    """

    __tablename__ = "user_prefs"

    user_key = Column(String(64), primary_key=True)
    notify = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<UserPrefs {self.user_key[:8]} notify={self.notify}>"


class PendingNotification(Base):
    """
    Aggregated notice waiting to be delivered to one user.

    At most one row per user: new events only increase the counters.
    Rows never store message text (only counts, the last sender's display
    name and a message id), and ephemeral PMs leave no sender name.
    """

    __tablename__ = "pending_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_key = Column(String(64), unique=True, nullable=False)

    pm_count = Column(Integer, default=0, nullable=False)
    mail_count = Column(Integer, default=0, nullable=False)
    reply_count = Column(Integer, default=0, nullable=False)
    mention_count = Column(Integer, default=0, nullable=False)

    # Last event (used for the single-event wording)
    last_sender = Column(String(32), nullable=True)
    last_ref = Column(Integer, nullable=True)

    # True after a failed delivery or when the user was not heard recently:
    # the notice then waits until the user is heard again on the mesh.
    wait_heard = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (Index("idx_pending_notif_created", "created_at"),)

    COUNT_FIELDS = ("pm_count", "mail_count", "reply_count", "mention_count")

    @property
    def total(self) -> int:
        return sum(int(getattr(self, f) or 0) for f in self.COUNT_FIELDS)

    def __repr__(self) -> str:
        return f"<PendingNotification {self.user_key[:8]} total={self.total}>"
