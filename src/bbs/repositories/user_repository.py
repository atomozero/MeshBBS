"""
User repository for data access operations.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .base_repository import BaseRepository
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType


# Minimum length of a public key prefix accepted as a user identifier
MIN_KEY_PREFIX_LENGTH = 8

# Identifiers made only of hex digits (real MeshCore keys are hex)
HEX_PATTERN = re.compile(r"^[0-9A-Fa-f]+$")

# Characters accepted in a key prefix lookup. Real keys are hex; plain
# alphanumerics are tolerated (legacy/test keys) but never LIKE wildcards.
KEY_PREFIX_PATTERN = re.compile(r"^[0-9A-Za-z]+$")

# Nicknames that look like a key prefix (hex-only, 6+ chars) are reserved:
# users without nickname are displayed as public_key[:8], so such a nick
# could be used to impersonate them.
RESERVED_HEX_NICK_PATTERN = re.compile(r"^[0-9A-Fa-f]{6,}$")

AMBIGUOUS_PREFIX_MESSAGE = (
    "[BBS] Prefisso chiave ambiguo: corrisponde a piu utenti. "
    "Usa un prefisso piu lungo"
)


class NicknameError(ValueError):
    """Raised when a nickname cannot be assigned (reserved or taken)."""


def is_hex_identifier(identifier: str) -> bool:
    """Return True if identifier contains only hexadecimal digits."""
    return bool(identifier) and bool(HEX_PATTERN.match(identifier))


def is_reserved_nickname(nickname: str) -> bool:
    """Return True if nickname looks like a public key prefix."""
    return bool(RESERVED_HEX_NICK_PATTERN.match(nickname or ""))


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
        Get user by nickname (exact match, case-insensitive).

        No LIKE pattern is involved, so '_' and '%' in the nickname are
        matched literally.

        Args:
            nickname: The nickname to search for

        Returns:
            User or None if not found (or if the match is ambiguous)
        """
        if not nickname:
            return None
        matches = (
            self.session.query(User)
            .filter(func.lower(User.nickname) == nickname.lower())
            .order_by(User.id)
            .limit(5)
            .all()
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Legacy duplicates differing only in case: accept only an
            # exact-case match, never guess.
            exact = [u for u in matches if u.nickname == nickname]
            if len(exact) == 1:
                return exact[0]
        return None

    def is_nickname_taken(
        self, nickname: str, exclude_public_key: Optional[str] = None
    ) -> bool:
        """
        Check whether a nickname is already used (case-insensitive).

        Args:
            nickname: Nickname to check
            exclude_public_key: Ignore this user (e.g. the one renaming)

        Returns:
            True if another user already owns the nickname
        """
        q = self.session.query(User.id).filter(
            func.lower(User.nickname) == nickname.lower()
        )
        if exclude_public_key is not None:
            q = q.filter(User.public_key != exclude_public_key)
        return q.first() is not None

    def set_nickname(self, public_key: str, nickname: str) -> Optional[User]:
        """
        Set nickname for a user.

        Case-insensitive uniqueness is checked here and enforced by the
        unique index ix_users_nickname_lower: a concurrent writer that wins
        the race makes the flush fail, reported as NicknameError.

        Args:
            public_key: The user's public key
            nickname: New nickname

        Returns:
            Updated user or None if not found

        Raises:
            NicknameError: if the nickname is reserved or already taken
        """
        if nickname is not None:
            if is_reserved_nickname(nickname):
                raise NicknameError(
                    "Nick non valido: non puo sembrare una chiave pubblica"
                )
            if self.is_nickname_taken(nickname, exclude_public_key=public_key):
                raise NicknameError(f"Nick '{nickname}' gia in uso")

        user = self.get_by_public_key(public_key)
        if user:
            old_nickname = user.nickname
            try:
                with self.session.begin_nested():
                    user.nickname = nickname
                    self.session.flush()
            except IntegrityError:
                raise NicknameError(f"Nick '{nickname}' gia in uso") from None

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

    def find_by_key_prefix(self, prefix: str) -> List[User]:
        """
        Find users whose public key starts with a hex prefix.

        The prefix must be alphanumeric (real keys are hex) and at least
        MIN_KEY_PREFIX_LENGTH chars; matching is case-insensitive and LIKE
        wildcards are escaped (autoescape) in any case.

        Args:
            prefix: Public key prefix

        Returns:
            Up to 2 matching users (enough to detect ambiguity)
        """
        if len(prefix) < MIN_KEY_PREFIX_LENGTH or not KEY_PREFIX_PATTERN.match(
            prefix
        ):
            return []
        return (
            self.session.query(User)
            .filter(
                func.lower(User.public_key).startswith(
                    prefix.lower(), autoescape=True
                )
            )
            .order_by(User.id)
            .limit(2)
            .all()
        )

    def resolve_user(self, identifier: str) -> Tuple[Optional[User], Optional[str]]:
        """
        Resolve a user identifier (nickname or public key prefix).

        Hex identifiers that match a key prefix are resolved as keys first
        (defense against nicknames impersonating a key prefix). A prefix
        matching more than one user is refused as ambiguous.

        Args:
            identifier: Nickname or public key prefix (min 8 hex chars)

        Returns:
            (user, None) on success, (None, error_message) if ambiguous,
            (None, None) if not found
        """
        identifier = (identifier or "").strip()
        if not identifier:
            return None, None

        # Hex identifiers: key prefix wins over nickname (defense in depth
        # against nicknames that mimic a key prefix).
        if is_hex_identifier(identifier):
            user, error = self._resolve_key_prefix(identifier)
            if user or error:
                return user, error

        user = self.get_by_nickname(identifier)
        if user:
            return user, None

        if not is_hex_identifier(identifier):
            return self._resolve_key_prefix(identifier)

        return None, None

    def _resolve_key_prefix(
        self, prefix: str
    ) -> Tuple[Optional[User], Optional[str]]:
        """Resolve a key prefix, refusing ambiguous matches."""
        matches = self.find_by_key_prefix(prefix)
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, AMBIGUOUS_PREFIX_MESSAGE
        return None, None

    def find_user(self, identifier: str) -> Optional[User]:
        """
        Find a user by nickname or public key prefix.

        Ambiguous key prefixes return None (never an arbitrary match).
        Use resolve_user() to get the reason.

        Args:
            identifier: Nickname or public key prefix (min 8 chars)

        Returns:
            User or None if not found / ambiguous
        """
        user, _ = self.resolve_user(identifier)
        return user

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
