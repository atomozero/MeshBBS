"""
Tests for /who command.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User


class TestWhoCommand:
    """Tests for /who command."""

    @pytest.mark.asyncio
    async def test_who_no_users(self, db_session: Session, test_sender_key: str):
        """Test /who with no other active users."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        # The calling user will be created, so they will be active
        assert "attiv" in response.lower()

    @pytest.mark.asyncio
    async def test_who_shows_active_user(self, db_session: Session, test_sender_key: str):
        """Test /who shows the current user as active."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        assert "[BBS]" in response
        # User's short key should appear
        assert test_sender_key[:8] in response or "1" in response

    @pytest.mark.asyncio
    async def test_who_with_multiple_users(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /who shows multiple active users."""
        # Create first user by calling a command
        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch("/help", test_sender_key)

        # Create second user
        await dispatcher.dispatch("/help", test_sender_key_2)

        # Now check /who
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        # Should show at least 2 users
        assert "2" in response or (test_sender_key[:8] in response and test_sender_key_2[:8] in response)

    @pytest.mark.asyncio
    async def test_who_with_nickname(self, db_session: Session, test_sender_key: str):
        """Test /who shows nickname instead of key."""
        dispatcher = CommandDispatcher(session=db_session)

        # Set nickname first
        await dispatcher.dispatch("/nick Mario", test_sender_key)

        # Check /who
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        assert "Mario" in response

    @pytest.mark.asyncio
    async def test_who_with_hours_argument(self, db_session: Session, test_sender_key: str):
        """Test /who with custom hours argument."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who 12", test_sender_key)

        assert response is not None
        assert "12h" in response

    @pytest.mark.asyncio
    async def test_who_invalid_hours(self, db_session: Session, test_sender_key: str):
        """Test /who with invalid hours argument."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who abc", test_sender_key)

        assert response is not None
        assert "uso" in response.lower() or "example" in response.lower() or "/who" in response.lower()

    @pytest.mark.asyncio
    async def test_who_negative_hours(self, db_session: Session, test_sender_key: str):
        """Test /who with negative hours."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who -5", test_sender_key)

        assert response is not None
        assert "positivo" in response.lower() or "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_who_max_hours_limit(self, db_session: Session, test_sender_key: str):
        """Test /who caps hours at maximum."""
        dispatcher = CommandDispatcher(session=db_session)
        # 1000 hours should be capped to 168 (MAX_HOURS)
        response = await dispatcher.dispatch("/who 1000", test_sender_key)

        assert response is not None
        # Should work but cap at 168h
        assert "168h" in response or "attiv" in response.lower()

    @pytest.mark.asyncio
    async def test_who_shows_admin_indicator(self, db_session: Session, test_sender_key: str):
        """Test /who shows [A] for admin users."""
        # Create admin user
        admin_user = User(
            public_key=test_sender_key,
            nickname="AdminUser",
            is_admin=True,
            last_seen=datetime.utcnow()
        )
        db_session.add(admin_user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        assert "[A]" in response

    @pytest.mark.asyncio
    async def test_who_shows_moderator_indicator(self, db_session: Session, test_sender_key: str):
        """Test /who shows [M] for moderator users."""
        # Create moderator user
        mod_user = User(
            public_key=test_sender_key,
            nickname="ModUser",
            is_moderator=True,
            last_seen=datetime.utcnow()
        )
        db_session.add(mod_user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        assert "[M]" in response

    @pytest.mark.asyncio
    async def test_who_excludes_banned_users(self, db_session: Session, test_sender_key: str):
        """Test /who does not show banned users."""
        # Create banned user
        banned_key = "C" * 64
        banned_user = User(
            public_key=banned_key,
            nickname="BannedUser",
            is_banned=True,
            last_seen=datetime.utcnow()
        )
        db_session.add(banned_user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/who", test_sender_key)

        assert response is not None
        assert "BannedUser" not in response

    @pytest.mark.asyncio
    async def test_who_alias_users(self, db_session: Session, test_sender_key: str):
        """Test /users alias works."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/users", test_sender_key)

        assert response is not None
        assert "[BBS]" in response
        assert "attiv" in response.lower()

    @pytest.mark.asyncio
    async def test_who_alias_online(self, db_session: Session, test_sender_key: str):
        """Test /online alias works."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/online", test_sender_key)

        assert response is not None
        assert "[BBS]" in response
        assert "attiv" in response.lower()

    @pytest.mark.asyncio
    async def test_who_inactive_users_not_shown(self, db_session: Session, test_sender_key: str):
        """Test /who does not show users inactive beyond the time window."""
        # Create old user (inactive for 48 hours)
        old_key = "D" * 64
        old_user = User(
            public_key=old_key,
            nickname="OldUser",
            last_seen=datetime.utcnow() - timedelta(hours=48)
        )
        db_session.add(old_user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        # Check with 12 hour window
        response = await dispatcher.dispatch("/who 12", test_sender_key)

        assert response is not None
        assert "OldUser" not in response
