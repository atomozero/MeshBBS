"""
Tests for privacy and GDPR compliance features.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime, timedelta

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType
from bbs.privacy import RetentionManager, check_sqlcipher_available, PrivacyInfo
from bbs.commands.msg_cmd import (
    add_ephemeral_message,
    get_ephemeral_messages,
    _ephemeral_messages,
)


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
def admin_user(db_session, sender_key):
    user = User(public_key=sender_key, nickname="AdminUser", is_admin=True)
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
def retention_manager(db_session):
    return RetentionManager(db_session)


@pytest.fixture(autouse=True)
def clear_ephemeral():
    """Clear ephemeral messages before each test."""
    _ephemeral_messages.clear()
    yield
    _ephemeral_messages.clear()


# ============================================
# Test Retention Manager
# ============================================

class TestRetentionManager:
    """Tests for the retention manager."""

    def test_cleanup_old_pms(self, db_session, retention_manager, sender_key, other_key):
        """Test cleanup of old private messages."""
        # Create users
        user1 = User(public_key=sender_key)
        user2 = User(public_key=other_key)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create old PM (40 days ago)
        old_pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_key,
            body="Old message",
            timestamp=datetime.utcnow() - timedelta(days=40),
        )
        db_session.add(old_pm)

        # Create recent PM (5 days ago)
        recent_pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_key,
            body="Recent message",
            timestamp=datetime.utcnow() - timedelta(days=5),
        )
        db_session.add(recent_pm)
        db_session.commit()

        # Run cleanup with 30 day retention
        deleted = retention_manager.cleanup_old_private_messages(30)

        assert deleted == 1  # Only old PM deleted

        # Verify recent PM still exists
        remaining = db_session.query(PrivateMessage).count()
        assert remaining == 1

    def test_cleanup_old_logs(self, db_session, retention_manager, sender_key):
        """Test cleanup of old activity logs."""
        # Create old log entry (100 days ago)
        old_log = ActivityLog(
            event_type=EventType.MESSAGE_POSTED.value,
            user_key=sender_key,
            details="Old activity",
            timestamp=datetime.utcnow() - timedelta(days=100),
        )
        db_session.add(old_log)

        # Create recent log (10 days ago)
        recent_log = ActivityLog(
            event_type=EventType.MESSAGE_POSTED.value,
            user_key=sender_key,
            details="Recent activity",
            timestamp=datetime.utcnow() - timedelta(days=10),
        )
        db_session.add(recent_log)
        db_session.commit()

        # Run cleanup with 90 day retention
        deleted = retention_manager.cleanup_old_activity_logs(90)

        assert deleted == 1  # Only old log deleted

        # Verify recent log still exists
        remaining = db_session.query(ActivityLog).count()
        assert remaining == 1

    def test_cleanup_zero_retention_keeps_all(self, db_session, retention_manager, sender_key, other_key):
        """Test that 0 retention days keeps everything."""
        user1 = User(public_key=sender_key)
        user2 = User(public_key=other_key)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create old PM
        old_pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_key,
            body="Very old",
            timestamp=datetime.utcnow() - timedelta(days=365),
        )
        db_session.add(old_pm)
        db_session.commit()

        # Run cleanup with 0 retention (keep forever)
        deleted = retention_manager.cleanup_old_private_messages(0)

        assert deleted == 0
        assert db_session.query(PrivateMessage).count() == 1

    def test_run_full_cleanup(self, db_session, retention_manager, sender_key, other_key):
        """Test full cleanup run."""
        user1 = User(public_key=sender_key)
        user2 = User(public_key=other_key)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create old data
        old_pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_key,
            body="Old",
            timestamp=datetime.utcnow() - timedelta(days=40),
        )
        old_log = ActivityLog(
            event_type=EventType.MESSAGE_POSTED.value,
            timestamp=datetime.utcnow() - timedelta(days=100),
        )
        db_session.add_all([old_pm, old_log])
        db_session.commit()

        # Run cleanup
        pms_deleted, logs_deleted = retention_manager.run_cleanup(
            pm_retention_days=30,
            log_retention_days=90,
        )

        assert pms_deleted == 1
        assert logs_deleted == 1

    def test_get_retention_stats(self, db_session, retention_manager, sender_key, other_key):
        """Test retention statistics."""
        user1 = User(public_key=sender_key)
        user2 = User(public_key=other_key)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Create mix of old and new data
        # i=0: 0 days (now), i=1: 10 days, i=2: 20 days, i=3: 30 days, i=4: 40 days
        for i in range(5):
            db_session.add(PrivateMessage(
                sender_key=sender_key,
                recipient_key=other_key,
                body=f"PM {i}",
                timestamp=datetime.utcnow() - timedelta(days=i * 10),
            ))
        db_session.commit()

        stats = retention_manager.get_retention_stats(pm_retention_days=25)

        assert stats["total_pms"] == 5
        # With 25 days retention, expired are: 30 days (i=3), 40 days (i=4) = 2 messages
        assert stats["expired_pms"] == 2
        assert stats["pm_retention_days"] == 25


# ============================================
# Test Ephemeral Messages
# ============================================

class TestEphemeralMessages:
    """Tests for ephemeral (non-saved) messages."""

    def test_add_ephemeral_message(self):
        """Test adding ephemeral message."""
        add_ephemeral_message(
            recipient_key="recipient123",
            sender_key="sender123",
            sender_name="TestSender",
            message="Hello!",
        )

        assert "recipient123" in _ephemeral_messages
        assert len(_ephemeral_messages["recipient123"]) == 1
        assert _ephemeral_messages["recipient123"][0]["message"] == "Hello!"

    def test_get_ephemeral_messages_clears(self):
        """Test that getting ephemeral messages clears them."""
        add_ephemeral_message(
            recipient_key="recipient123",
            sender_key="sender123",
            sender_name="TestSender",
            message="Hello!",
        )

        messages = get_ephemeral_messages("recipient123")

        assert len(messages) == 1
        assert messages[0]["message"] == "Hello!"

        # Should be empty now
        messages2 = get_ephemeral_messages("recipient123")
        assert len(messages2) == 0

    def test_ephemeral_limit(self):
        """Test ephemeral messages limit per recipient."""
        for i in range(60):
            add_ephemeral_message(
                recipient_key="recipient123",
                sender_key="sender123",
                sender_name="Sender",
                message=f"Message {i}",
            )

        # Should only keep last 50
        assert len(_ephemeral_messages["recipient123"]) == 50

    @pytest.mark.asyncio
    async def test_ephemeral_msg_command(self, dispatcher, sender_key, user, other_user):
        """Test /msg! command sends ephemeral message."""
        response = await dispatcher.dispatch("!msg! OtherUser Ciao!", sender_key)

        assert "effimero" in response
        assert "non salvato" in response

        # Check ephemeral storage
        messages = get_ephemeral_messages(other_user.public_key)
        assert len(messages) == 1
        assert messages[0]["message"] == "Ciao!"

    @pytest.mark.asyncio
    async def test_ephemeral_not_in_database(self, db_session, dispatcher, sender_key, user, other_user):
        """Test ephemeral messages are NOT saved to database."""
        initial_count = db_session.query(PrivateMessage).count()

        await dispatcher.dispatch("!msg! OtherUser Secret!", sender_key)

        # Database should have same count
        final_count = db_session.query(PrivateMessage).count()
        assert final_count == initial_count

    @pytest.mark.asyncio
    async def test_inbox_shows_ephemeral(self, dispatcher, sender_key, user, other_user, other_key):
        """Test /inbox shows ephemeral messages."""
        # Add ephemeral message for user
        add_ephemeral_message(
            recipient_key=sender_key,
            sender_key=other_key,
            sender_name="OtherUser",
            message="Ephemeral hello!",
        )

        response = await dispatcher.dispatch("!inbox", sender_key)

        assert "effimeri" in response
        assert "OtherUser" in response
        assert "spariscono" in response

    @pytest.mark.asyncio
    async def test_inbox_ephemeral_disappear_after_read(self, dispatcher, sender_key, user, other_key):
        """Test ephemeral messages disappear after inbox read."""
        add_ephemeral_message(
            recipient_key=sender_key,
            sender_key=other_key,
            sender_name="Other",
            message="Gone after read",
        )

        # First read
        await dispatcher.dispatch("!inbox", sender_key)

        # Second read should not show ephemeral
        response = await dispatcher.dispatch("!inbox", sender_key)
        assert "effimeri" not in response


# ============================================
# Test GDPR Command
# ============================================

class TestGdprCommand:
    """Tests for GDPR information command."""

    @pytest.mark.asyncio
    async def test_gdpr_command(self, dispatcher, sender_key, user):
        """Test /gdpr command shows privacy info."""
        response = await dispatcher.dispatch("!gdpr", sender_key)

        assert "GDPR" in response
        assert "Retention" in response
        assert "Crittografia" in response

    @pytest.mark.asyncio
    async def test_privacy_alias(self, dispatcher, sender_key, user):
        """Test /privacy alias."""
        response = await dispatcher.dispatch("/privacy", sender_key)

        assert "GDPR" in response


# ============================================
# Test Cleanup Command
# ============================================

class TestCleanupCommand:
    """Tests for cleanup command."""

    @pytest.mark.asyncio
    async def test_cleanup_non_admin_denied(self, dispatcher, sender_key, user):
        """Test non-admin cannot run cleanup."""
        response = await dispatcher.dispatch("!cleanup", sender_key)

        assert "Permesso negato" in response

    @pytest.mark.asyncio
    async def test_cleanup_dry_run(self, dispatcher, sender_key, admin_user):
        """Test cleanup dry-run mode."""
        response = await dispatcher.dispatch("!cleanup --dry-run", sender_key)

        assert "preview" in response or "dry-run" in response
        assert "da eliminare" in response

    @pytest.mark.asyncio
    async def test_cleanup_executes(self, db_session, dispatcher, sender_key, admin_user, other_key):
        """Test cleanup actually deletes data."""
        # Create other user
        other = User(public_key=other_key)
        db_session.add(other)
        db_session.commit()

        # Create old PM
        old_pm = PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_key,
            body="Old",
            timestamp=datetime.utcnow() - timedelta(days=40),
        )
        db_session.add(old_pm)
        db_session.commit()

        response = await dispatcher.dispatch("!cleanup", sender_key)

        assert "completato" in response or "eliminat" in response


# ============================================
# Test MyData Command
# ============================================

class TestMyDataCommand:
    """Tests for mydata command."""

    @pytest.mark.asyncio
    async def test_mydata_command(self, dispatcher, sender_key, user):
        """Test /mydata shows user's stored data."""
        response = await dispatcher.dispatch("!mydata", sender_key)

        assert "dati salvati" in response
        assert "Nickname" in response
        assert "Messaggi pubblici" in response

    @pytest.mark.asyncio
    async def test_mydata_shows_counts(self, db_session, dispatcher, sender_key, user, other_user):
        """Test /mydata shows correct counts."""
        # Create area
        area = Area(name="test_area")
        db_session.add(area)
        db_session.commit()

        # Add messages
        for i in range(3):
            db_session.add(Message(
                area_id=area.id,
                sender_key=sender_key,
                body=f"Message {i}",
            ))

        # Add PM
        db_session.add(PrivateMessage(
            sender_key=sender_key,
            recipient_key=other_user.public_key,
            body="PM",
        ))
        db_session.commit()

        response = await dispatcher.dispatch("!mydata", sender_key)

        assert "Messaggi pubblici: 3" in response
        assert "PM inviati: 1" in response


# ============================================
# Test Privacy Info
# ============================================

class TestPrivacyInfo:
    """Tests for privacy info utilities."""

    def test_privacy_notice(self):
        """Test privacy notice text."""
        notice = PrivacyInfo.get_privacy_notice()

        assert "Privacy" in notice
        assert "!msg!" in notice

    def test_gdpr_info(self):
        """Test GDPR info text."""
        info = PrivacyInfo.get_gdpr_info(
            pm_retention_days=30,
            log_retention_days=90,
            encryption_enabled=False,
        )

        assert "30 giorni" in info
        assert "90 giorni" in info
        assert "disattiva" in info

    def test_gdpr_info_encryption_enabled(self):
        """Test GDPR info with encryption enabled."""
        info = PrivacyInfo.get_gdpr_info(
            pm_retention_days=30,
            log_retention_days=90,
            encryption_enabled=True,
        )

        assert "attiva" in info

    def test_gdpr_info_forever_retention(self):
        """Test GDPR info with no retention limit."""
        info = PrivacyInfo.get_gdpr_info(
            pm_retention_days=0,
            log_retention_days=0,
            encryption_enabled=False,
        )

        assert "indefinito" in info


# ============================================
# Test SQLCipher Detection
# ============================================

class TestSQLCipher:
    """Tests for SQLCipher detection."""

    def test_check_sqlcipher_available(self):
        """Test SQLCipher availability check."""
        # This test just ensures the function runs without error
        result = check_sqlcipher_available()
        assert isinstance(result, bool)
