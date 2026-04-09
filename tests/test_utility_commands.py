"""
Tests for utility commands: delpm, clear, stats, info, whois.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.private_message import PrivateMessage


# Test fixtures
@pytest.fixture
def sender_key():
    return "sender123456789"


@pytest.fixture
def other_key():
    return "other1234567890"


@pytest.fixture
def dispatcher(db_session):
    return CommandDispatcher(db_session)


@pytest.fixture
def user(db_session, sender_key):
    user = User(public_key=sender_key, nickname="TestUser")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def other_user(db_session, other_key):
    user = User(public_key=other_key, nickname="OtherUser")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def area(db_session):
    # Check if area already exists
    existing = db_session.query(Area).filter_by(name="generale").first()
    if existing:
        return existing
    area = Area(name="generale", description="Area generale")
    db_session.add(area)
    db_session.commit()
    return area


# ============================================
# Test /delpm command
# ============================================

class TestDelPmCommand:
    """Tests for the /delpm command."""

    @pytest.mark.asyncio
    async def test_delpm_no_args(self, dispatcher, sender_key, user):
        """Test /delpm without arguments."""
        response = await dispatcher.dispatch("/delpm", sender_key)
        assert "Uso: /delpm" in response

    @pytest.mark.asyncio
    async def test_delpm_invalid_id(self, dispatcher, sender_key, user):
        """Test /delpm with invalid ID."""
        response = await dispatcher.dispatch("/delpm abc", sender_key)
        assert "ID non valido" in response

    @pytest.mark.asyncio
    async def test_delpm_not_found(self, dispatcher, sender_key, user):
        """Test /delpm with non-existent message."""
        response = await dispatcher.dispatch("/delpm 999", sender_key)
        assert "non trovato" in response

    @pytest.mark.asyncio
    async def test_delpm_as_recipient(self, db_session, dispatcher, sender_key, user, other_user):
        """Test deleting a received message."""
        # Create a PM from other to sender
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test message"
        )
        db_session.add(pm)
        db_session.commit()
        pm_id = pm.id

        response = await dispatcher.dispatch(f"/delpm {pm_id}", sender_key)
        assert "eliminato" in response

        # Verify deleted
        deleted = db_session.query(PrivateMessage).filter_by(id=pm_id).first()
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delpm_as_sender(self, db_session, dispatcher, sender_key, user, other_user):
        """Test deleting a sent message."""
        # Create a PM from sender to other
        pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_user.public_key,
            body="Test message"
        )
        db_session.add(pm)
        db_session.commit()
        pm_id = pm.id

        response = await dispatcher.dispatch(f"/delpm {pm_id}", sender_key)
        assert "eliminato" in response

    @pytest.mark.asyncio
    async def test_delpm_not_involved(self, db_session, dispatcher, sender_key, user, other_user):
        """Test cannot delete messages not involved in."""
        third_key = "third1234567890"
        third_user = User(public_key=third_key)
        db_session.add(third_user)
        db_session.commit()

        # Create PM between other users (not involving sender)
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=third_key,
            body="Test"
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch(f"/delpm {pm.id}", sender_key)
        assert "non trovato" in response

    @pytest.mark.asyncio
    async def test_delpm_with_hash_prefix(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /delpm #id format."""
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test"
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch(f"/delpm #{pm.id}", sender_key)
        assert "eliminato" in response

    @pytest.mark.asyncio
    async def test_delpm_alias_deletepm(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /deletepm alias."""
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test"
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch(f"/deletepm {pm.id}", sender_key)
        assert "eliminato" in response

    @pytest.mark.asyncio
    async def test_delpm_alias_rmpm(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /rmpm alias."""
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test"
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch(f"/rmpm {pm.id}", sender_key)
        assert "eliminato" in response


# ============================================
# Test /clear command
# ============================================

class TestClearCommand:
    """Tests for the /clear command."""

    @pytest.mark.asyncio
    async def test_clear_no_unread(self, dispatcher, sender_key, user):
        """Test /clear with no unread messages."""
        response = await dispatcher.dispatch("/clear", sender_key)
        assert "Nessun messaggio non letto" in response

    @pytest.mark.asyncio
    async def test_clear_marks_all_read(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /clear marks all messages as read."""
        # Create multiple unread PMs
        for i in range(5):
            pm = PrivateMessage(
                sender_key=other_user.public_key,
                recipient_key=sender_key,
                body=f"Message {i}",
                is_read=False
            )
            db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch("/clear", sender_key)
        assert "5 messaggi marcati come letti" in response

        # Verify all are read
        unread = (
            db_session.query(PrivateMessage)
            .filter_by(recipient_key=sender_key, is_read=False)
            .count()
        )
        assert unread == 0

    @pytest.mark.asyncio
    async def test_clear_only_affects_unread(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /clear only affects unread messages."""
        # Create mix of read and unread
        for i in range(3):
            pm = PrivateMessage(
                sender_key=other_user.public_key,
                recipient_key=sender_key,
                body=f"Unread {i}",
                is_read=False
            )
            db_session.add(pm)

        for i in range(2):
            pm = PrivateMessage(
                sender_key=other_user.public_key,
                recipient_key=sender_key,
                body=f"Read {i}",
                is_read=True
            )
            db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch("/clear", sender_key)
        assert "3 messaggi" in response

    @pytest.mark.asyncio
    async def test_clear_alias_readall(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /readall alias."""
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test",
            is_read=False
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch("/readall", sender_key)
        assert "marcati come letti" in response

    @pytest.mark.asyncio
    async def test_clear_alias_markread(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /markread alias."""
        pm = PrivateMessage(
            sender_key=other_user.public_key,
            recipient_key=sender_key,
            body="Test",
            is_read=False
        )
        db_session.add(pm)
        db_session.commit()

        response = await dispatcher.dispatch("/markread", sender_key)
        assert "marcati come letti" in response


# ============================================
# Test /stats command
# ============================================

class TestStatsCommand:
    """Tests for the /stats command."""

    @pytest.mark.asyncio
    async def test_stats_basic(self, dispatcher, sender_key, user):
        """Test basic /stats output."""
        response = await dispatcher.dispatch("/stats", sender_key)
        assert "[BBS] Statistiche:" in response
        assert "Utenti:" in response
        assert "Messaggi:" in response
        assert "Aree:" in response
        assert "PM:" in response

    @pytest.mark.asyncio
    async def test_stats_shows_user_count(self, db_session, dispatcher, sender_key, user):
        """Test /stats shows correct user count."""
        # Add more users
        for i in range(5):
            db_session.add(User(public_key=f"user{i}1234567890"))
        db_session.commit()

        response = await dispatcher.dispatch("/stats", sender_key)
        assert "6 totali" in response  # 1 original + 5 new

    @pytest.mark.asyncio
    async def test_stats_shows_active_users(self, db_session, dispatcher, sender_key, user):
        """Test /stats shows active users in last 24h."""
        # Add an old user
        old_user = User(public_key="olduser1234567890")
        old_user.last_seen = datetime.utcnow() - timedelta(days=5)
        db_session.add(old_user)
        db_session.commit()

        response = await dispatcher.dispatch("/stats", sender_key)
        # Old user shouldn't be counted as active
        assert "attivi (24h)" in response

    @pytest.mark.asyncio
    async def test_stats_shows_message_count(self, db_session, dispatcher, sender_key, user, area):
        """Test /stats shows message count."""
        # Add messages
        for i in range(10):
            msg = Message(
                area_id=area.id,
                sender_key=sender_key,
                body=f"Message {i}"
            )
            db_session.add(msg)
        db_session.commit()

        response = await dispatcher.dispatch("/stats", sender_key)
        assert "10 totali" in response

    @pytest.mark.asyncio
    async def test_stats_shows_area_count(self, db_session, dispatcher, sender_key, user):
        """Test /stats shows area count."""
        # Get current counts
        current_public = db_session.query(Area).filter(Area.is_public == True).count()
        current_total = db_session.query(Area).count()

        # Add areas
        for i in range(3):
            db_session.add(Area(name=f"statarea{i}", is_public=True))
        db_session.add(Area(name="stathidden", is_public=False))
        db_session.commit()

        response = await dispatcher.dispatch("/stats", sender_key)
        expected_public = current_public + 3
        expected_total = current_total + 4
        assert f"{expected_public} pubbliche" in response
        assert f"{expected_total} totali" in response

    @pytest.mark.asyncio
    async def test_stats_alias_stat(self, dispatcher, sender_key, user):
        """Test /stat alias."""
        response = await dispatcher.dispatch("/stat", sender_key)
        assert "Statistiche:" in response

    @pytest.mark.asyncio
    async def test_stats_alias_statistics(self, dispatcher, sender_key, user):
        """Test /statistics alias."""
        response = await dispatcher.dispatch("/statistics", sender_key)
        assert "Statistiche:" in response


# ============================================
# Test /info command
# ============================================

class TestInfoCommand:
    """Tests for the /info command."""

    @pytest.mark.asyncio
    async def test_info_basic(self, dispatcher, sender_key, user):
        """Test basic /info output."""
        response = await dispatcher.dispatch("/info", sender_key)
        assert "[BBS] MeshCore BBS" in response
        assert "v1.0.0" in response

    @pytest.mark.asyncio
    async def test_info_shows_user_count(self, db_session, dispatcher, sender_key, user):
        """Test /info shows registered users."""
        response = await dispatcher.dispatch("/info", sender_key)
        assert "Utenti registrati:" in response

    @pytest.mark.asyncio
    async def test_info_shows_area_count(self, db_session, dispatcher, sender_key, user, area):
        """Test /info shows public areas."""
        response = await dispatcher.dispatch("/info", sender_key)
        assert "Aree pubbliche:" in response

    @pytest.mark.asyncio
    async def test_info_shows_protocol(self, dispatcher, sender_key, user):
        """Test /info shows protocol info."""
        response = await dispatcher.dispatch("/info", sender_key)
        assert "MeshCore LoRa" in response

    @pytest.mark.asyncio
    async def test_info_shows_license(self, dispatcher, sender_key, user):
        """Test /info shows license."""
        response = await dispatcher.dispatch("/info", sender_key)
        assert "MIT" in response

    @pytest.mark.asyncio
    async def test_info_alias_about(self, dispatcher, sender_key, user):
        """Test /about alias."""
        response = await dispatcher.dispatch("/about", sender_key)
        assert "MeshCore BBS" in response

    @pytest.mark.asyncio
    async def test_info_alias_version(self, dispatcher, sender_key, user):
        """Test /version alias."""
        response = await dispatcher.dispatch("/version", sender_key)
        assert "v1.0.0" in response


# ============================================
# Test /whois command
# ============================================

class TestWhoisCommand:
    """Tests for the /whois command."""

    @pytest.mark.asyncio
    async def test_whois_no_args(self, dispatcher, sender_key, user):
        """Test /whois without arguments."""
        response = await dispatcher.dispatch("/whois", sender_key)
        assert "Uso: /whois" in response

    @pytest.mark.asyncio
    async def test_whois_not_found(self, dispatcher, sender_key, user):
        """Test /whois with non-existent user."""
        response = await dispatcher.dispatch("/whois unknown", sender_key)
        assert "non trovato" in response

    @pytest.mark.asyncio
    async def test_whois_by_nickname(self, dispatcher, sender_key, user, other_user):
        """Test /whois by nickname."""
        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Profilo: OtherUser" in response

    @pytest.mark.asyncio
    async def test_whois_by_public_key(self, dispatcher, sender_key, user, other_user, other_key):
        """Test /whois by public key."""
        response = await dispatcher.dispatch(f"/whois {other_key[:8]}", sender_key)
        assert "Profilo: OtherUser" in response

    @pytest.mark.asyncio
    async def test_whois_shows_role(self, dispatcher, sender_key, user, other_user):
        """Test /whois shows role."""
        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Ruolo: Utente" in response

    @pytest.mark.asyncio
    async def test_whois_shows_admin_role(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /whois shows admin role."""
        other_user.is_admin = True
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Ruolo: Admin" in response

    @pytest.mark.asyncio
    async def test_whois_shows_moderator_role(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /whois shows moderator role."""
        other_user.is_moderator = True
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Ruolo: Moderatore" in response

    @pytest.mark.asyncio
    async def test_whois_shows_registration_date(self, dispatcher, sender_key, user, other_user):
        """Test /whois shows registration date."""
        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Registrato:" in response

    @pytest.mark.asyncio
    async def test_whois_shows_last_seen(self, dispatcher, sender_key, user, other_user):
        """Test /whois shows last seen."""
        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Ultimo accesso:" in response

    @pytest.mark.asyncio
    async def test_whois_shows_message_count(self, db_session, dispatcher, sender_key, user, other_user, area):
        """Test /whois shows message count."""
        # Add messages for other_user
        for i in range(5):
            db_session.add(Message(
                area_id=area.id,
                sender_key=other_user.public_key,
                body=f"Message {i}"
            ))
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Messaggi: 5" in response

    @pytest.mark.asyncio
    async def test_whois_shows_banned_status(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /whois shows banned status."""
        other_user.ban("Test reason")
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "BANNATO" in response

    @pytest.mark.asyncio
    async def test_whois_shows_muted_status(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /whois shows muted status."""
        other_user.mute("Test reason")
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Silenziato" in response

    @pytest.mark.asyncio
    async def test_whois_shows_kicked_status(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /whois shows kicked status."""
        other_user.kick(30, "Test reason")
        db_session.commit()

        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Kick" in response

    @pytest.mark.asyncio
    async def test_whois_shows_public_key(self, dispatcher, sender_key, user, other_user, other_key):
        """Test /whois shows truncated public key."""
        response = await dispatcher.dispatch("/whois OtherUser", sender_key)
        assert "Chiave:" in response
        assert other_key[:16] in response

    @pytest.mark.asyncio
    async def test_whois_alias_user(self, dispatcher, sender_key, user, other_user):
        """Test /user alias."""
        response = await dispatcher.dispatch("/user OtherUser", sender_key)
        assert "Profilo:" in response

    @pytest.mark.asyncio
    async def test_whois_alias_profile(self, dispatcher, sender_key, user, other_user):
        """Test /profile alias."""
        response = await dispatcher.dispatch("/profile OtherUser", sender_key)
        assert "Profilo:" in response

    @pytest.mark.asyncio
    async def test_whois_self(self, dispatcher, sender_key, user):
        """Test /whois on self."""
        response = await dispatcher.dispatch("/whois TestUser", sender_key)
        assert "Profilo: TestUser" in response


# ============================================
# Test command workflow
# ============================================

class TestUtilityWorkflow:
    """Integration tests for utility commands."""

    @pytest.mark.asyncio
    async def test_full_pm_workflow(self, db_session, dispatcher, sender_key, user, other_user):
        """Test sending, reading, and deleting PM."""
        # Send a PM (using msg command)
        response = await dispatcher.dispatch("/msg OtherUser Ciao!", sender_key)
        assert "inviato" in response

        # Get PM count for sender
        from bbs.models.private_message import PrivateMessage
        pm = db_session.query(PrivateMessage).filter_by(sender_key=sender_key).first()
        assert pm is not None

        # Delete the PM
        response = await dispatcher.dispatch(f"/delpm {pm.id}", sender_key)
        assert "eliminato" in response

        # Verify it's gone
        pm = db_session.query(PrivateMessage).filter_by(sender_key=sender_key).first()
        assert pm is None

    @pytest.mark.asyncio
    async def test_stats_after_activity(self, db_session, dispatcher, sender_key, user, area):
        """Test stats reflect real activity."""
        # Post some messages
        for i in range(5):
            await dispatcher.dispatch(f"/post #generale Message {i}", sender_key)

        # Check stats
        response = await dispatcher.dispatch("/stats", sender_key)
        assert "5 totali" in response or "Messaggi:" in response
