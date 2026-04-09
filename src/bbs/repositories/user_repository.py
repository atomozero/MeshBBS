"""
User repository for data access operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy.orm import Session

from .base_repository import BaseRepository
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType


class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""

    model = User

    def __init__(self, session: Session):
        super().__init__(session)

    def get_by_public_key(self, public_key: str) -> Optional[User]:
        """
        Get user by their MeshCore public key.

        Args:
            public_key: The user's public key

        Returns:
            User or None if not found
        """
        return (
            self.session.query(User).filter(User.public_key == public_key).first()
        )

    def get_or_create(self, public_key: str) -> tuple[User, bool]:
        """
        Get existing user or create a new one.

        Args:
            public_key: The user's public key

        Returns:
            Tuple of (User, created) where created is True if new user
        """
        user = self.get_by_public_key(public_key)

        if user:
            user.update_last_seen()
            return user, False

        # Create new user
        user = User(public_key=public_key)
        self.session.add(user)

        # Log first seen event
        self.session.add(
            ActivityLog.log(
                EventType.USER_FIRST_SEEN,
                user_key=public_key,
                details="New user first contact",
            )
        )

        return user, True

    def get_by_nickname(self, nickname: str) -> Optional[User]:
        """
        Get user by nickname.

        Args:
            nickname: The nickname to search for

        Returns:
            User or None if not found
        """
        return (
            self.session.query(User)
            .filter(User.nickname.ilike(nickname))
            .first()
        )

    def set_nickname(self, public_key: str, nickname: str) -> Optional[User]:
        """
        Set nickname for a user.

        Args:
            public_key: The user's public key
            nickname: New nickname

        Returns:
            Updated user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            old_nickname = user.nickname
            user.nickname = nickname

            self.session.add(
                ActivityLog.log(
                    EventType.USER_NICKNAME_SET,
                    user_key=public_key,
                    details=f"Nickname changed: {old_nickname} -> {nickname}",
                )
            )

        return user

    def get_active_users(self, hours: int = 24) -> List[User]:
        """
        Get users active in the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of active users
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return (
            self.session.query(User)
            .filter(User.last_seen >= cutoff)
            .filter(User.is_banned == False)
            .order_by(User.last_seen.desc())
            .all()
        )

    def get_admins(self) -> List[User]:
        """
        Get all admin users.

        Returns:
            List of admin users
        """
        return (
            self.session.query(User).filter(User.is_admin == True).all()
        )

    def ban_user(self, public_key: str, reason: Optional[str] = None) -> Optional[User]:
        """
        Ban a user.

        Args:
            public_key: User's public key
            reason: Reason for ban

        Returns:
            Banned user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.ban(reason)
            self.session.add(
                ActivityLog.log(
                    EventType.USER_BANNED,
                    user_key=public_key,
                    details=f"Reason: {reason}" if reason else "No reason given",
                )
            )
        return user

    def unban_user(self, public_key: str) -> Optional[User]:
        """
        Remove ban from a user.

        Args:
            public_key: User's public key

        Returns:
            Unbanned user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.unban()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_UNBANNED,
                    user_key=public_key,
                )
            )
        return user

    def mute_user(self, public_key: str, reason: Optional[str] = None) -> Optional[User]:
        """
        Mute a user (can read but cannot post).

        Args:
            public_key: User's public key
            reason: Reason for mute

        Returns:
            Muted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.mute(reason)
            self.session.add(
                ActivityLog.log(
                    EventType.USER_MUTED,
                    user_key=public_key,
                    details=f"Reason: {reason}" if reason else "No reason given",
                )
            )
        return user

    def unmute_user(self, public_key: str) -> Optional[User]:
        """
        Remove mute from a user.

        Args:
            public_key: User's public key

        Returns:
            Unmuted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.unmute()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_UNMUTED,
                    user_key=public_key,
                )
            )
        return user

    def find_user(self, identifier: str) -> Optional[User]:
        """
        Find a user by nickname or public key prefix.

        Args:
            identifier: Nickname or public key prefix (min 8 chars)

        Returns:
            User or None if not found
        """
        # Try nickname first
        user = self.get_by_nickname(identifier)
        if user:
            return user

        # Try public key prefix (min 8 chars)
        if len(identifier) >= 8:
            return (
                self.session.query(User)
                .filter(User.public_key.startswith(identifier))
                .first()
            )

        return None

    def promote_to_moderator(self, public_key: str) -> Optional[User]:
        """
        Promote a user to moderator.

        Args:
            public_key: User's public key

        Returns:
            Promoted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            old_role = user.role_display
            user.promote_to_moderator()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_PROMOTED,
                    user_key=public_key,
                    details=f"Promoted from {old_role} to Moderatore",
                )
            )
        return user

    def promote_to_admin(self, public_key: str) -> Optional[User]:
        """
        Promote a user to admin.

        Args:
            public_key: User's public key

        Returns:
            Promoted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            old_role = user.role_display
            user.promote_to_admin()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_PROMOTED,
                    user_key=public_key,
                    details=f"Promoted from {old_role} to Admin",
                )
            )
        return user

    def demote_from_moderator(self, public_key: str) -> Optional[User]:
        """
        Remove moderator status from a user.

        Args:
            public_key: User's public key

        Returns:
            Demoted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            old_role = user.role_display
            user.demote_from_moderator()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_DEMOTED,
                    user_key=public_key,
                    details=f"Demoted from {old_role} to Utente",
                )
            )
        return user

    def demote_from_admin(self, public_key: str) -> Optional[User]:
        """
        Remove admin status from a user (keeps moderator).

        Args:
            public_key: User's public key

        Returns:
            Demoted user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.demote_from_admin()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_DEMOTED,
                    user_key=public_key,
                    details="Demoted from Admin to Moderatore",
                )
            )
        return user

    def get_moderators(self) -> List[User]:
        """
        Get all moderator users (not admins).

        Returns:
            List of moderator users
        """
        return (
            self.session.query(User)
            .filter(User.is_moderator == True)
            .filter(User.is_admin == False)
            .all()
        )

    def kick_user(
        self, public_key: str, minutes: int, reason: Optional[str] = None
    ) -> Optional[User]:
        """
        Kick a user for a specified duration.

        Args:
            public_key: User's public key
            minutes: Duration of kick in minutes
            reason: Reason for kick

        Returns:
            Kicked user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.kick(minutes, reason)
            self.session.add(
                ActivityLog.log(
                    EventType.USER_KICKED,
                    user_key=public_key,
                    details=f"Kicked for {minutes} min. Reason: {reason}" if reason else f"Kicked for {minutes} min",
                )
            )
        return user

    def unkick_user(self, public_key: str) -> Optional[User]:
        """
        Remove kick from a user.

        Args:
            public_key: User's public key

        Returns:
            Unkicked user or None if not found
        """
        user = self.get_by_public_key(public_key)
        if user:
            user.unkick()
            self.session.add(
                ActivityLog.log(
                    EventType.USER_UNKICKED,
                    user_key=public_key,
                )
            )
        return user
