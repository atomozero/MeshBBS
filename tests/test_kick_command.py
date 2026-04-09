"""
Tests for kick/unkick commands.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.area import Area


class TestKickCommand:
    """Tests for /kick command."""

    @pytest.mark.asyncio
    async def test_kick_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /kick without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /kick."""
        target = User(public_key=test_sender_key_2, nickname="Target")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick Target", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_user_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /kick with non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick NonExistent", admin_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_default_duration(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test kick with default duration (30 minutes)."""
        target = User(public_key=test_sender_key_2, nickname="Troublemaker")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick Troublemaker", admin_sender_key)

        assert response is not None
        assert "espulso" in response.lower()
        assert "30 minuti" in response.lower()

        db_session.refresh(target)
        assert target.is_kicked is True

    @pytest.mark.asyncio
    async def test_kick_custom_duration(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test kick with custom duration."""
        target = User(public_key=test_sender_key_2, nickname="Spammer")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick Spammer 60", admin_sender_key)

        assert response is not None
        assert "espulso" in response.lower()
        assert "60 minuti" in response.lower()

        db_session.refresh(target)
        assert target.is_kicked is True

    @pytest.mark.asyncio
    async def test_kick_with_reason(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test kick with reason."""
        target = User(public_key=test_sender_key_2, nickname="BadUser")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick BadUser 15 comportamento scorretto", admin_sender_key)

        assert response is not None
        assert "espulso" in response.lower()
        assert "comportamento scorretto" in response.lower()

        db_session.refresh(target)
        assert target.kick_reason == "comportamento scorretto"

    @pytest.mark.asyncio
    async def test_kick_max_duration(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test kick duration is capped at max."""
        target = User(public_key=test_sender_key_2, nickname="LongKick")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        # Try to kick for 10000 minutes (should be capped to 1440)
        response = await dispatcher.dispatch("/kick LongKick 10000", admin_sender_key)

        assert response is not None
        assert "1440 minuti" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_cannot_kick_self(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test admin cannot kick themselves."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/kick {admin_sender_key[:8]}", admin_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_cannot_kick_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot kick another admin."""
        other_admin = User(public_key=test_sender_key_2, nickname="OtherAdmin", is_admin=True)
        db_session.add(other_admin)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick OtherAdmin", admin_sender_key)

        assert response is not None
        assert "non puoi espellere un admin" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_already_kicked(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test kicking already kicked user."""
        target = User(public_key=test_sender_key_2, nickname="AlreadyKicked")
        target.kick(60)  # Already kicked for 60 minutes
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick AlreadyKicked", admin_sender_key)

        assert response is not None
        assert "già espulso" in response.lower()
        assert "min rimanenti" in response.lower()

    @pytest.mark.asyncio
    async def test_kick_banned_user(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot kick a banned user."""
        target = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/kick Banned", admin_sender_key)

        assert response is not None
        assert "già bannato" in response.lower()


class TestUnkickCommand:
    """Tests for /unkick command."""

    @pytest.mark.asyncio
    async def test_unkick_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /unkick without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unkick", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_unkick_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /unkick."""
        target = User(public_key=test_sender_key_2, nickname="Kicked")
        target.kick(60)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unkick Kicked", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_unkick_success(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test successful unkick."""
        target = User(public_key=test_sender_key_2, nickname="Forgiven")
        target.kick(60)
        db_session.add(target)
        db_session.commit()

        assert target.is_kicked is True

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unkick Forgiven", admin_sender_key)

        assert response is not None
        assert "può nuovamente accedere" in response.lower()

        db_session.refresh(target)
        assert target.is_kicked is False

    @pytest.mark.asyncio
    async def test_unkick_not_kicked(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test unkicking user who is not kicked."""
        target = User(public_key=test_sender_key_2, nickname="Active")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unkick Active", admin_sender_key)

        assert response is not None
        assert "non è espulso" in response.lower()

    @pytest.mark.asyncio
    async def test_unkick_user_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /unkick with non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unkick NonExistent", admin_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()


class TestKickExpiration:
    """Tests for kick expiration logic."""

    def test_is_kicked_when_active(self, db_session: Session):
        """Test is_kicked returns True when kick is active."""
        user = User(public_key="X" * 64)
        user.kick(60)

        assert user.is_kicked is True

    def test_is_kicked_when_expired(self, db_session: Session):
        """Test is_kicked returns False when kick has expired."""
        user = User(public_key="X" * 64)
        # Set kicked_until to the past
        user.kicked_until = datetime.utcnow() - timedelta(minutes=5)

        assert user.is_kicked is False

    def test_is_kicked_when_never_kicked(self, db_session: Session):
        """Test is_kicked returns False when never kicked."""
        user = User(public_key="X" * 64)

        assert user.is_kicked is False

    def test_kick_remaining_minutes(self, db_session: Session):
        """Test kick_remaining_minutes calculation."""
        user = User(public_key="X" * 64)
        user.kick(60)

        remaining = user.kick_remaining_minutes
        assert 58 <= remaining <= 60  # Allow some tolerance

    def test_kick_remaining_minutes_expired(self, db_session: Session):
        """Test kick_remaining_minutes returns 0 when expired."""
        user = User(public_key="X" * 64)
        user.kicked_until = datetime.utcnow() - timedelta(minutes=5)

        assert user.kick_remaining_minutes == 0


class TestKickEffects:
    """Tests for kick effects on user access."""

    @pytest.mark.asyncio
    async def test_kicked_user_access_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test kicked user gets access denied."""
        user = User(public_key=test_sender_key)
        user.kick(60)
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/help", test_sender_key)

        assert response is not None
        assert "accesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_kicked_user_cannot_post(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test kicked user cannot post."""
        user = User(public_key=test_sender_key)
        user.kick(60)
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post Test", test_sender_key)

        assert response is not None
        assert "accesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_expired_kick_allows_access(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test user can access after kick expires."""
        user = User(public_key=test_sender_key)
        # Set kicked_until to the past
        user.kicked_until = datetime.utcnow() - timedelta(minutes=5)
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/help", test_sender_key)

        assert response is not None
        # Should NOT be access denied
        assert "accesso negato" not in response.lower()

    @pytest.mark.asyncio
    async def test_unkicked_user_can_post(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test user can post after being unkicked."""
        target = User(public_key=test_sender_key_2, nickname="WasKicked")
        target.kick(60)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Unkick user
        await dispatcher.dispatch("/unkick WasKicked", admin_sender_key)
        db_session.commit()

        # Now user should be able to post
        response = await dispatcher.dispatch("/post Back online!", test_sender_key_2)

        assert response is not None
        assert "pubblicato" in response.lower()


class TestKickVsBanVsMute:
    """Tests comparing kick, ban, and mute behaviors."""

    def test_is_active_with_kick(self, db_session: Session):
        """Test is_active returns False when kicked."""
        user = User(public_key="X" * 64)
        user.kick(60)

        assert user.is_active() is False

    def test_is_active_with_ban(self, db_session: Session):
        """Test is_active returns False when banned."""
        user = User(public_key="X" * 64, is_banned=True)

        assert user.is_active() is False

    def test_is_active_with_mute(self, db_session: Session):
        """Test is_active returns True when muted (mute doesn't block access)."""
        user = User(public_key="X" * 64, is_muted=True)

        assert user.is_active() is True  # Muted users can still access

    def test_can_post_when_kicked(self, db_session: Session):
        """Test can_post returns False when kicked."""
        user = User(public_key="X" * 64)
        user.kick(60)

        assert user.can_post() is False

    def test_can_post_when_muted(self, db_session: Session):
        """Test can_post returns False when muted."""
        user = User(public_key="X" * 64, is_muted=True)

        assert user.can_post() is False
