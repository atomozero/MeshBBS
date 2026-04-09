"""
Tests for admin commands (ban, unban, mute, unmute).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.area import Area


class TestBanCommand:
    """Tests for /ban command."""

    @pytest.mark.asyncio
    async def test_ban_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /ban without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /ban."""
        # Create target user
        target = User(public_key=test_sender_key_2, nickname="Target")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!ban Target", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_user_not_found(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test /ban with non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban NonExistent", admin_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_success(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test successful ban."""
        target = User(public_key=test_sender_key_2, nickname="BadUser")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban BadUser", admin_sender_key)

        assert response is not None
        assert "bannato" in response.lower()

        # Verify user is banned
        db_session.refresh(target)
        assert target.is_banned is True

    @pytest.mark.asyncio
    async def test_ban_with_reason(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test ban with reason."""
        target = User(public_key=test_sender_key_2, nickname="Spammer")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban Spammer spam ripetuto", admin_sender_key)

        assert response is not None
        assert "bannato" in response.lower()
        assert "spam ripetuto" in response.lower()

        db_session.refresh(target)
        assert target.ban_reason == "spam ripetuto"

    @pytest.mark.asyncio
    async def test_ban_cannot_ban_self(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test admin cannot ban themselves."""
        dispatcher = CommandDispatcher(session=db_session)
        # Admin tries to ban themselves by key prefix
        response = await dispatcher.dispatch(f"!ban {admin_sender_key[:8]}", admin_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_cannot_ban_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot ban another admin."""
        other_admin = User(public_key=test_sender_key_2, nickname="OtherAdmin", is_admin=True)
        db_session.add(other_admin)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban OtherAdmin", admin_sender_key)

        assert response is not None
        assert "non puoi bannare un admin" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_already_banned(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test banning already banned user."""
        target = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!ban Banned", admin_sender_key)

        assert response is not None
        assert "già bannato" in response.lower()

    @pytest.mark.asyncio
    async def test_ban_by_public_key(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test ban by public key prefix."""
        target = User(public_key=test_sender_key_2)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!ban {test_sender_key_2[:8]}", admin_sender_key)

        assert response is not None
        assert "bannato" in response.lower()


class TestUnbanCommand:
    """Tests for /unban command."""

    @pytest.mark.asyncio
    async def test_unban_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /unban without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unban", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_unban_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /unban."""
        target = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unban Banned", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_unban_success(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test successful unban."""
        target = User(public_key=test_sender_key_2, nickname="Forgiven", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unban Forgiven", admin_sender_key)

        assert response is not None
        assert "rimosso" in response.lower()

        db_session.refresh(target)
        assert target.is_banned is False

    @pytest.mark.asyncio
    async def test_unban_not_banned(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test unbanning user who is not banned."""
        target = User(public_key=test_sender_key_2, nickname="Active")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unban Active", admin_sender_key)

        assert response is not None
        assert "non è bannato" in response.lower()


class TestMuteCommand:
    """Tests for /mute command."""

    @pytest.mark.asyncio
    async def test_mute_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /mute without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /mute."""
        target = User(public_key=test_sender_key_2, nickname="Target")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute Target", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_success(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test successful mute."""
        target = User(public_key=test_sender_key_2, nickname="Talkative")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute Talkative", admin_sender_key)

        assert response is not None
        assert "silenziato" in response.lower()

        db_session.refresh(target)
        assert target.is_muted is True

    @pytest.mark.asyncio
    async def test_mute_with_reason(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test mute with reason."""
        target = User(public_key=test_sender_key_2, nickname="OffTopic")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute OffTopic discussione off-topic", admin_sender_key)

        assert response is not None
        assert "silenziato" in response.lower()
        assert "off-topic" in response.lower()

        db_session.refresh(target)
        assert target.mute_reason == "discussione off-topic"

    @pytest.mark.asyncio
    async def test_mute_cannot_mute_self(
        self, db_session: Session, admin_sender_key: str
    ):
        """Test admin cannot mute themselves."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!mute {admin_sender_key[:8]}", admin_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_cannot_mute_admin(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot mute an admin."""
        other_admin = User(public_key=test_sender_key_2, nickname="OtherAdmin", is_admin=True)
        db_session.add(other_admin)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute OtherAdmin", admin_sender_key)

        assert response is not None
        assert "non puoi silenziare un admin" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_already_muted(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test muting already muted user."""
        target = User(public_key=test_sender_key_2, nickname="Silent", is_muted=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute Silent", admin_sender_key)

        assert response is not None
        assert "già silenziato" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_banned_user(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot mute a banned user (already blocked)."""
        target = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!mute Banned", admin_sender_key)

        assert response is not None
        assert "bannato" in response.lower()

    @pytest.mark.asyncio
    async def test_mute_alias_silence(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test /silence alias works."""
        target = User(public_key=test_sender_key_2, nickname="Loud")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/silence Loud", admin_sender_key)

        assert response is not None
        assert "silenziato" in response.lower()


class TestUnmuteCommand:
    """Tests for /unmute command."""

    @pytest.mark.asyncio
    async def test_unmute_no_args(self, db_session: Session, admin_sender_key: str):
        """Test /unmute without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unmute", admin_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_unmute_non_admin_denied(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test non-admin cannot use /unmute."""
        target = User(public_key=test_sender_key_2, nickname="Muted", is_muted=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unmute Muted", test_sender_key)

        assert response is not None
        assert "permesso negato" in response.lower()

    @pytest.mark.asyncio
    async def test_unmute_success(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test successful unmute."""
        target = User(public_key=test_sender_key_2, nickname="Muted", is_muted=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unmute Muted", admin_sender_key)

        assert response is not None
        assert "può nuovamente scrivere" in response.lower()

        db_session.refresh(target)
        assert target.is_muted is False

    @pytest.mark.asyncio
    async def test_unmute_not_muted(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test unmuting user who is not muted."""
        target = User(public_key=test_sender_key_2, nickname="Active")
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unmute Active", admin_sender_key)

        assert response is not None
        assert "non è silenziato" in response.lower()

    @pytest.mark.asyncio
    async def test_unmute_alias_unsilence(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str
    ):
        """Test /unsilence alias works."""
        target = User(public_key=test_sender_key_2, nickname="Quiet", is_muted=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/unsilence Quiet", admin_sender_key)

        assert response is not None
        assert "può nuovamente scrivere" in response.lower()


class TestMuteEffects:
    """Tests for mute effects on posting."""

    @pytest.mark.asyncio
    async def test_muted_user_cannot_post(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test muted user cannot post messages."""
        # Create muted user
        user = User(public_key=test_sender_key, is_muted=True)
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!post Test message", test_sender_key)

        assert response is not None
        assert "non puoi pubblicare" in response.lower()

    @pytest.mark.asyncio
    async def test_muted_user_cannot_reply(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test muted user cannot reply to messages."""
        # Create users
        muted_user = User(public_key=test_sender_key, is_muted=True)
        other_user = User(public_key=test_sender_key_2)
        db_session.add_all([muted_user, other_user])
        db_session.commit()

        # Create a message to reply to
        from bbs.models.message import Message
        msg = Message(area_id=sample_areas[0].id, sender_key=test_sender_key_2, body="Original")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!reply {msg.id} My reply", test_sender_key)

        assert response is not None
        assert "non puoi pubblicare" in response.lower()

    @pytest.mark.asyncio
    async def test_muted_user_cannot_send_pm(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test muted user cannot send private messages."""
        muted_user = User(public_key=test_sender_key, is_muted=True)
        recipient = User(public_key=test_sender_key_2, nickname="Recipient")
        db_session.add_all([muted_user, recipient])
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!msg Recipient Hello", test_sender_key)

        assert response is not None
        assert "non puoi inviare" in response.lower()

    @pytest.mark.asyncio
    async def test_muted_user_can_read(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test muted user can still read messages."""
        muted_user = User(public_key=test_sender_key, is_muted=True)
        author = User(public_key=test_sender_key_2)
        db_session.add_all([muted_user, author])
        db_session.commit()

        # Create a message
        from bbs.models.message import Message
        msg = Message(area_id=sample_areas[0].id, sender_key=test_sender_key_2, body="Readable content")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!read {msg.id}", test_sender_key)

        assert response is not None
        assert "readable content" in response.lower()

    @pytest.mark.asyncio
    async def test_unmuted_user_can_post(
        self, db_session: Session, admin_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test user can post after being unmuted."""
        # Create and mute user
        target = User(public_key=test_sender_key_2, nickname="WasMuted", is_muted=True)
        db_session.add(target)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Unmute user
        await dispatcher.dispatch("!unmute WasMuted", admin_sender_key)
        db_session.commit()

        # Now user should be able to post
        response = await dispatcher.dispatch("!post Back to posting!", test_sender_key_2)

        assert response is not None
        assert "pubblicato" in response.lower()


class TestBannedUserAccess:
    """Tests for banned user access restrictions."""

    @pytest.mark.asyncio
    async def test_banned_user_access_denied(
        self, db_session: Session, test_sender_key: str
    ):
        """Test banned user gets access denied on any command."""
        user = User(public_key=test_sender_key, is_banned=True)
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!help", test_sender_key)

        assert response is not None
        assert "accesso negato" in response.lower()
