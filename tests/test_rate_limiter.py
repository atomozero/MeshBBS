"""
Tests for the rate limiter module.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta
import time

from bbs.rate_limiter import RateLimiter, UserRateInfo


class TestUserRateInfo:
    """Tests for UserRateInfo dataclass."""

    def test_add_command(self):
        """Test adding a command timestamp."""
        info = UserRateInfo()
        assert info.last_command is None

        info.add_command()

        assert info.last_command is not None
        assert len(info.command_times) == 1

    def test_get_commands_in_window(self):
        """Test counting commands in time window."""
        info = UserRateInfo()

        # Add some commands
        for _ in range(5):
            info.add_command()

        count = info.get_commands_in_window(60)
        assert count == 5

    def test_seconds_since_last_no_commands(self):
        """Test seconds_since_last with no commands."""
        info = UserRateInfo()
        assert info.seconds_since_last() == float("inf")

    def test_seconds_since_last_with_command(self):
        """Test seconds_since_last after a command."""
        info = UserRateInfo()
        info.add_command()

        # Should be very small (just executed)
        assert info.seconds_since_last() < 1

    def test_is_blocked_not_blocked(self):
        """Test is_blocked when not blocked."""
        info = UserRateInfo()
        assert not info.is_blocked()

    def test_is_blocked_when_blocked(self):
        """Test is_blocked when blocked."""
        info = UserRateInfo()
        info.block_for(60)

        assert info.is_blocked()

    def test_is_blocked_expired(self):
        """Test is_blocked when block has expired."""
        info = UserRateInfo()
        # Set block in the past
        info.blocked_until = datetime.utcnow() - timedelta(seconds=1)

        assert not info.is_blocked()
        assert info.blocked_until is None  # Should be cleared

    def test_block_for(self):
        """Test blocking for specified duration."""
        info = UserRateInfo()
        info.block_for(30)

        assert info.blocked_until is not None
        remaining = (info.blocked_until - datetime.utcnow()).total_seconds()
        assert 29 <= remaining <= 30


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        limiter = RateLimiter()

        assert limiter.min_interval == 1.0
        assert limiter.max_per_minute == 30
        assert limiter.block_duration == 60

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        limiter = RateLimiter(
            min_interval=2.0,
            max_per_minute=20,
            block_duration=120,
        )

        assert limiter.min_interval == 2.0
        assert limiter.max_per_minute == 20
        assert limiter.block_duration == 120

    def test_check_new_user_allowed(self):
        """Test that a new user is allowed."""
        limiter = RateLimiter()
        allowed, error = limiter.check("user123")

        assert allowed is True
        assert error is None

    def test_check_too_fast(self):
        """Test rate limiting when too fast."""
        limiter = RateLimiter(min_interval=1.0)

        # First command - allowed
        limiter.record("user123")

        # Second command immediately - should be blocked
        allowed, error = limiter.check("user123")

        assert allowed is False
        assert "Troppo veloce" in error

    def test_check_after_interval(self):
        """Test check succeeds after interval passes."""
        limiter = RateLimiter(min_interval=0.1)

        # First command
        limiter.record("user123")

        # Wait for interval
        time.sleep(0.15)

        # Should be allowed now
        allowed, error = limiter.check("user123")

        assert allowed is True
        assert error is None

    def test_check_max_per_minute_exceeded(self):
        """Test blocking when max per minute is exceeded."""
        limiter = RateLimiter(min_interval=0, max_per_minute=3, block_duration=60)

        # Execute 3 commands
        for _ in range(3):
            limiter.record("user123")

        # Fourth command should trigger block
        allowed, error = limiter.check("user123")

        assert allowed is False
        assert "Limite comandi superato" in error

    def test_check_blocked_user(self):
        """Test that blocked users are denied."""
        limiter = RateLimiter()
        info = limiter._get_user_info("user123")
        info.block_for(60)

        allowed, error = limiter.check("user123")

        assert allowed is False
        assert "Troppi comandi" in error

    def test_whitelist_bypasses_limits(self):
        """Test that whitelisted users bypass rate limiting."""
        limiter = RateLimiter(min_interval=1.0)

        limiter.add_to_whitelist("admin123")

        # Record a command
        limiter.record("admin123")

        # Should still be allowed immediately
        allowed, error = limiter.check("admin123")

        assert allowed is True
        assert error is None

    def test_remove_from_whitelist(self):
        """Test removing user from whitelist."""
        limiter = RateLimiter(min_interval=1.0)

        limiter.add_to_whitelist("admin123")
        limiter.remove_from_whitelist("admin123")

        # Record a command
        limiter.record("admin123")

        # Should now be rate limited
        allowed, error = limiter.check("admin123")

        assert allowed is False

    def test_check_and_record(self):
        """Test convenience method check_and_record."""
        limiter = RateLimiter(min_interval=1.0)

        # First call - should be allowed and recorded
        allowed1, error1 = limiter.check_and_record("user123")

        assert allowed1 is True
        assert error1 is None

        # Second call - should be denied
        allowed2, error2 = limiter.check_and_record("user123")

        assert allowed2 is False
        assert error2 is not None

    def test_get_user_stats(self):
        """Test getting user stats."""
        limiter = RateLimiter()
        limiter.record("user123")
        limiter.record("user123")

        stats = limiter.get_user_stats("user123")

        assert stats["whitelisted"] is False
        assert stats["commands_last_minute"] == 2
        assert stats["is_blocked"] is False

    def test_get_user_stats_whitelisted(self):
        """Test getting stats for whitelisted user."""
        limiter = RateLimiter()
        limiter.add_to_whitelist("admin123")

        stats = limiter.get_user_stats("admin123")

        assert stats["whitelisted"] is True

    def test_reset_user(self):
        """Test resetting user rate info."""
        limiter = RateLimiter()

        # Record some commands
        for _ in range(5):
            limiter.record("user123")

        # Reset
        limiter.reset_user("user123")

        # Stats should be fresh
        stats = limiter.get_user_stats("user123")
        assert stats["commands_last_minute"] == 0

    def test_cleanup_old_entries(self):
        """Test cleaning up old entries."""
        limiter = RateLimiter()

        # Create user with old activity
        info = limiter._get_user_info("old_user")
        info.last_command = datetime.utcnow() - timedelta(hours=48)

        # Create user with recent activity
        limiter.record("recent_user")

        # Cleanup with 24 hour threshold
        removed = limiter.cleanup_old_entries(max_age_hours=24)

        assert removed == 1
        assert "old_user" not in limiter._users
        assert "recent_user" in limiter._users


class TestRateLimiterIntegration:
    """Integration tests for rate limiter with dispatcher."""

    @pytest.mark.asyncio
    async def test_dispatcher_with_rate_limiter(self, db_session):
        """Test dispatcher respects rate limiting."""
        from bbs.commands.dispatcher import CommandDispatcher
        from bbs.models.user import User

        # Create a user
        user = User(public_key="user12345678", nickname="TestUser")
        db_session.add(user)
        db_session.commit()

        # Create dispatcher with rate limiter
        limiter = RateLimiter(min_interval=1.0)
        dispatcher = CommandDispatcher(db_session, rate_limiter=limiter)

        # First command should succeed
        response1 = await dispatcher.dispatch("!help", "user12345678")
        assert "Comandi" in response1

        # Second command immediately should be rate limited
        response2 = await dispatcher.dispatch("!help", "user12345678")
        assert "Troppo veloce" in response2

    @pytest.mark.asyncio
    async def test_admin_bypasses_rate_limit(self, db_session):
        """Test that admins bypass rate limiting."""
        from bbs.commands.dispatcher import CommandDispatcher
        from bbs.models.user import User

        # Create an admin user
        admin = User(public_key="admin1234567", nickname="Admin", is_admin=True)
        db_session.add(admin)
        db_session.commit()

        # Create dispatcher with rate limiter
        limiter = RateLimiter(min_interval=1.0)
        dispatcher = CommandDispatcher(db_session, rate_limiter=limiter)

        # First command
        response1 = await dispatcher.dispatch("!help", "admin1234567")
        assert "Comandi" in response1

        # Second command immediately - admin should not be rate limited
        response2 = await dispatcher.dispatch("!help", "admin1234567")
        assert "Comandi" in response2
        assert "Troppo veloce" not in response2
