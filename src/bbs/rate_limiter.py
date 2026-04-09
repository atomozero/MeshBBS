"""
Rate limiting for MeshCore BBS.

Prevents spam and abuse by limiting command frequency per user.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger("meshbbs.ratelimit")


@dataclass
class UserRateInfo:
    """Tracks rate limiting info for a user."""

    # Timestamps of recent commands
    command_times: deque = field(default_factory=lambda: deque(maxlen=100))

    # Last command timestamp
    last_command: Optional[datetime] = None

    # Temporary block until this time
    blocked_until: Optional[datetime] = None

    def add_command(self) -> None:
        """Record a command execution."""
        now = datetime.utcnow()
        self.command_times.append(now)
        self.last_command = now

    def get_commands_in_window(self, seconds: int) -> int:
        """Count commands in the last N seconds."""
        cutoff = datetime.utcnow() - timedelta(seconds=seconds)
        return sum(1 for t in self.command_times if t > cutoff)

    def seconds_since_last(self) -> float:
        """Seconds since last command."""
        if self.last_command is None:
            return float("inf")
        return (datetime.utcnow() - self.last_command).total_seconds()

    def is_blocked(self) -> bool:
        """Check if user is temporarily blocked."""
        if self.blocked_until is None:
            return False
        if datetime.utcnow() >= self.blocked_until:
            self.blocked_until = None
            return False
        return True

    def block_for(self, seconds: int) -> None:
        """Block user for specified seconds."""
        self.blocked_until = datetime.utcnow() + timedelta(seconds=seconds)


class RateLimiter:
    """
    Rate limiter for BBS commands.

    Implements two types of limits:
    1. Minimum interval between commands (anti-flood)
    2. Maximum commands per time window (anti-spam)
    """

    def __init__(
        self,
        min_interval: float = 1.0,
        max_per_minute: int = 30,
        block_duration: int = 60,
    ):
        """
        Initialize rate limiter.

        Args:
            min_interval: Minimum seconds between commands
            max_per_minute: Maximum commands per minute
            block_duration: Seconds to block after exceeding limit
        """
        self.min_interval = min_interval
        self.max_per_minute = max_per_minute
        self.block_duration = block_duration

        # Track per-user rate info
        self._users: Dict[str, UserRateInfo] = {}

        # Whitelist for admins/moderators (bypass rate limiting)
        self._whitelist: set = set()

    def _get_user_info(self, user_key: str) -> UserRateInfo:
        """Get or create rate info for user."""
        if user_key not in self._users:
            self._users[user_key] = UserRateInfo()
        return self._users[user_key]

    def add_to_whitelist(self, user_key: str) -> None:
        """Add user to whitelist (bypass rate limiting)."""
        self._whitelist.add(user_key)

    def remove_from_whitelist(self, user_key: str) -> None:
        """Remove user from whitelist."""
        self._whitelist.discard(user_key)

    def check(self, user_key: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user is allowed to execute a command.

        Args:
            user_key: User's public key

        Returns:
            Tuple of (allowed, error_message)
            If allowed is True, error_message is None
        """
        # Whitelist bypasses all limits
        if user_key in self._whitelist:
            return True, None

        info = self._get_user_info(user_key)

        # Check if blocked
        if info.is_blocked():
            remaining = (info.blocked_until - datetime.utcnow()).seconds
            return False, f"Troppi comandi. Riprova tra {remaining}s"

        # Check minimum interval
        if info.seconds_since_last() < self.min_interval:
            return False, "Troppo veloce. Attendi un momento"

        # Check commands per minute
        commands_last_minute = info.get_commands_in_window(60)
        if commands_last_minute >= self.max_per_minute:
            info.block_for(self.block_duration)
            logger.warning(f"Rate limit exceeded for {user_key[:8]}, blocked for {self.block_duration}s")
            return False, f"Limite comandi superato. Bloccato per {self.block_duration}s"

        return True, None

    def record(self, user_key: str) -> None:
        """
        Record a command execution.

        Call this AFTER successfully executing a command.

        Args:
            user_key: User's public key
        """
        if user_key in self._whitelist:
            return

        info = self._get_user_info(user_key)
        info.add_command()

    def check_and_record(self, user_key: str) -> Tuple[bool, Optional[str]]:
        """
        Check rate limit and record if allowed.

        Convenience method combining check() and record().

        Args:
            user_key: User's public key

        Returns:
            Tuple of (allowed, error_message)
        """
        allowed, error = self.check(user_key)
        if allowed:
            self.record(user_key)
        return allowed, error

    def get_user_stats(self, user_key: str) -> dict:
        """Get rate limiting stats for a user."""
        if user_key in self._whitelist:
            return {"whitelisted": True}

        info = self._get_user_info(user_key)
        return {
            "whitelisted": False,
            "commands_last_minute": info.get_commands_in_window(60),
            "seconds_since_last": info.seconds_since_last(),
            "is_blocked": info.is_blocked(),
            "blocked_until": info.blocked_until.isoformat() if info.blocked_until else None,
        }

    def reset_user(self, user_key: str) -> None:
        """Reset rate limiting for a user."""
        if user_key in self._users:
            del self._users[user_key]

    def cleanup_old_entries(self, max_age_hours: int = 24) -> int:
        """
        Remove old user entries to free memory.

        Args:
            max_age_hours: Remove entries older than this

        Returns:
            Number of entries removed
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
        to_remove = []

        for user_key, info in self._users.items():
            if info.last_command and info.last_command < cutoff:
                to_remove.append(user_key)

        for user_key in to_remove:
            del self._users[user_key]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} old rate limit entries")

        return len(to_remove)
