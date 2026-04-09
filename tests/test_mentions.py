"""
Tests for the mentions notification system.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime

from bbs.mentions import (
    MentionNotifier,
    Mention,
    get_mention_notifier,
    process_mentions_in_message,
    format_mentions_for_inbox,
    MENTION_PATTERN,
    _mention_notifier,
)
from bbs.models.user import User
from bbs.models.area import Area


@pytest.fixture
def notifier():
    """Create a fresh notifier for each test."""
    return MentionNotifier()


@pytest.fixture(autouse=True)
def reset_global_notifier():
    """Reset global notifier before each test."""
    import bbs.mentions
    bbs.mentions._mention_notifier = None
    yield
    bbs.mentions._mention_notifier = None


class TestMentionPattern:
    """Tests for the mention regex pattern."""

    def test_basic_mention(self):
        """Test basic @nickname detection."""
        text = "Ciao @Mario come stai?"
        matches = MENTION_PATTERN.findall(text)
        assert matches == ["Mario"]

    def test_multiple_mentions(self):
        """Test multiple mentions in one message."""
        text = "@Alice e @Bob, guardate questo!"
        matches = MENTION_PATTERN.findall(text)
        assert sorted(matches) == ["Alice", "Bob"]

    def test_mention_at_start(self):
        """Test mention at start of message."""
        text = "@Admin hai visto?"
        matches = MENTION_PATTERN.findall(text)
        assert matches == ["Admin"]

    def test_mention_at_end(self):
        """Test mention at end of message."""
        text = "Grazie a @Helper"
        matches = MENTION_PATTERN.findall(text)
        assert matches == ["Helper"]

    def test_mention_with_underscore(self):
        """Test mention with underscores."""
        text = "Chiedi a @john_doe"
        matches = MENTION_PATTERN.findall(text)
        assert matches == ["john_doe"]

    def test_mention_with_numbers(self):
        """Test mention with numbers."""
        text = "Ciao @user123"
        matches = MENTION_PATTERN.findall(text)
        assert matches == ["user123"]

    def test_no_mention_email(self):
        """Test that email-like patterns don't fully match."""
        text = "Scrivi a test@example.com"
        matches = MENTION_PATTERN.findall(text)
        # Should match 'example' but that's fine, we validate later
        assert "test" not in matches

    def test_no_mention_short_name(self):
        """Test that single-char names don't match."""
        text = "Vai a @x per info"
        matches = MENTION_PATTERN.findall(text)
        # Pattern requires at least 2 chars total
        assert matches == []

    def test_mention_case_preserved(self):
        """Test that case is preserved in matches."""
        text = "@ADMIN and @admin"
        matches = MENTION_PATTERN.findall(text)
        assert "ADMIN" in matches
        assert "admin" in matches


class TestMentionNotifier:
    """Tests for the MentionNotifier class."""

    def test_extract_mentions(self, notifier):
        """Test extracting mentions from text."""
        text = "Hey @Alice and @Bob, look at this!"
        mentions = notifier.extract_mentions(text)

        assert mentions == {"alice", "bob"}

    def test_extract_mentions_lowercase(self, notifier):
        """Test that extracted mentions are lowercase."""
        text = "@UPPERCASE and @MixedCase"
        mentions = notifier.extract_mentions(text)

        assert mentions == {"uppercase", "mixedcase"}

    def test_extract_mentions_deduplication(self, notifier):
        """Test that duplicate mentions are deduplicated."""
        text = "@alice said hi to @Alice"
        mentions = notifier.extract_mentions(text)

        assert len(mentions) == 1
        assert "alice" in mentions

    def test_create_mention(self, notifier):
        """Test creating a mention."""
        notifier.create_mention(
            recipient_key="recipient123",
            sender_key="sender123",
            sender_name="TestSender",
            message_id=42,
            area_name="generale",
            message_body="Hey @recipient, check this out!",
        )

        assert notifier.has_mentions("recipient123")
        assert notifier.get_mention_count("recipient123") == 1

    def test_get_mentions_clears_by_default(self, notifier):
        """Test that get_mentions clears mentions by default."""
        notifier.create_mention(
            recipient_key="user123",
            sender_key="sender",
            sender_name="Sender",
            message_id=1,
            area_name="test",
            message_body="Test",
        )

        # First get should return mentions
        mentions = notifier.get_mentions("user123")
        assert len(mentions) == 1

        # Second get should be empty
        mentions2 = notifier.get_mentions("user123")
        assert len(mentions2) == 0

    def test_get_mentions_without_clear(self, notifier):
        """Test get_mentions with clear=False."""
        notifier.create_mention(
            recipient_key="user123",
            sender_key="sender",
            sender_name="Sender",
            message_id=1,
            area_name="test",
            message_body="Test",
        )

        # Get without clearing
        mentions = notifier.get_mentions("user123", clear=False)
        assert len(mentions) == 1

        # Should still have mentions
        assert notifier.has_mentions("user123")

    def test_mention_limit(self, notifier):
        """Test that mentions are limited per user."""
        # Create more than the limit
        for i in range(60):
            notifier.create_mention(
                recipient_key="user123",
                sender_key="sender",
                sender_name="Sender",
                message_id=i,
                area_name="test",
                message_body=f"Message {i}",
            )

        # Should only keep MAX_MENTIONS_PER_USER
        assert notifier.get_mention_count("user123") == 50

    def test_mention_excerpt_truncation(self, notifier):
        """Test that long messages are truncated in excerpt."""
        long_message = "A" * 100  # 100 chars

        notifier.create_mention(
            recipient_key="user123",
            sender_key="sender",
            sender_name="Sender",
            message_id=1,
            area_name="test",
            message_body=long_message,
        )

        mentions = notifier.get_mentions("user123")
        assert len(mentions[0].excerpt) == 53  # 50 + "..."
        assert mentions[0].excerpt.endswith("...")

    def test_clear_mentions(self, notifier):
        """Test clearing mentions for a user."""
        notifier.create_mention(
            recipient_key="user123",
            sender_key="sender",
            sender_name="Sender",
            message_id=1,
            area_name="test",
            message_body="Test",
        )

        count = notifier.clear_mentions("user123")

        assert count == 1
        assert not notifier.has_mentions("user123")

    def test_get_stats(self, notifier):
        """Test getting mention system stats."""
        notifier.create_mention(
            recipient_key="user1",
            sender_key="sender",
            sender_name="Sender",
            message_id=1,
            area_name="test",
            message_body="Test",
        )
        notifier.create_mention(
            recipient_key="user2",
            sender_key="sender",
            sender_name="Sender",
            message_id=2,
            area_name="test",
            message_body="Test",
        )

        stats = notifier.get_stats()

        assert stats["users_with_mentions"] == 2
        assert stats["total_pending_mentions"] == 2


class TestGlobalNotifier:
    """Tests for global notifier instance."""

    def test_get_mention_notifier_creates_instance(self):
        """Test that get_mention_notifier creates an instance."""
        notifier = get_mention_notifier()
        assert notifier is not None
        assert isinstance(notifier, MentionNotifier)

    def test_get_mention_notifier_returns_same_instance(self):
        """Test that get_mention_notifier returns the same instance."""
        notifier1 = get_mention_notifier()
        notifier2 = get_mention_notifier()
        assert notifier1 is notifier2


class TestProcessMentions:
    """Tests for process_mentions_in_message function."""

    @pytest.fixture
    def setup_users(self, db_session):
        """Set up test users."""
        sender = User(public_key="sender12345678", nickname="Sender")
        alice = User(public_key="alice123456789", nickname="Alice")
        bob = User(public_key="bob1234567890", nickname="Bob")
        banned = User(public_key="banned12345678", nickname="Banned", is_banned=True)

        db_session.add_all([sender, alice, bob, banned])
        db_session.commit()

        return {"sender": sender, "alice": alice, "bob": bob, "banned": banned}

    def test_process_mention_creates_notification(self, db_session, setup_users):
        """Test that processing mentions creates notifications."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="Hey @Alice, check this out!",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        assert "Alice" in notified

        # Check notification was created
        notifier = get_mention_notifier()
        assert notifier.has_mentions("alice123456789")

    def test_process_mention_multiple_users(self, db_session, setup_users):
        """Test processing multiple mentions."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="@Alice and @Bob, look at this!",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        assert len(notified) == 2
        assert "Alice" in notified
        assert "Bob" in notified

    def test_process_mention_no_self_notify(self, db_session, setup_users):
        """Test that users don't notify themselves."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="I @Sender mention myself",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        assert "Sender" not in notified

    def test_process_mention_no_notify_banned(self, db_session, setup_users):
        """Test that banned users don't get notifications."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="Hey @Banned, you there?",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        assert "Banned" not in notified

    def test_process_mention_nonexistent_user(self, db_session, setup_users):
        """Test that nonexistent users are ignored."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="Hey @NonExistent, are you there?",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        assert len(notified) == 0

    def test_process_mention_case_insensitive(self, db_session, setup_users):
        """Test that mentions are case insensitive."""
        notified = process_mentions_in_message(
            session=db_session,
            message_body="Hey @ALICE and @alice!",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
        )

        # Should only notify once despite case variations
        assert notified.count("Alice") == 1


class TestFormatMentions:
    """Tests for format_mentions_for_inbox function."""

    def test_format_empty_mentions(self):
        """Test formatting empty mention list."""
        result = format_mentions_for_inbox([])
        assert result == ""

    def test_format_single_mention(self):
        """Test formatting single mention."""
        mentions = [
            Mention(
                recipient_key="user123",
                sender_key="sender123",
                sender_name="TestSender",
                message_id=42,
                area_name="generale",
                excerpt="Test message...",
            )
        ]

        result = format_mentions_for_inbox(mentions)

        assert "Menzioni (1)" in result
        assert "@TestSender" in result
        assert "#generale" in result
        assert "/read 42" in result

    def test_format_multiple_mentions(self):
        """Test formatting multiple mentions."""
        mentions = [
            Mention(
                recipient_key="user123",
                sender_key="sender1",
                sender_name="Alice",
                message_id=1,
                area_name="tech",
                excerpt="First mention",
            ),
            Mention(
                recipient_key="user123",
                sender_key="sender2",
                sender_name="Bob",
                message_id=2,
                area_name="generale",
                excerpt="Second mention",
            ),
        ]

        result = format_mentions_for_inbox(mentions)

        assert "Menzioni (2)" in result
        assert "@Alice" in result
        assert "@Bob" in result


class TestMentionsInCommands:
    """Integration tests for mentions in post/reply commands."""

    @pytest.fixture
    def setup_for_post(self, db_session):
        """Set up users and area for post tests."""
        sender = User(public_key="sender12345678", nickname="Sender")
        recipient = User(public_key="recipient12345", nickname="Recipient")

        db_session.add_all([sender, recipient])
        db_session.commit()

        # Get or create area (may already exist from conftest)
        from bbs.models.area import Area
        area = db_session.query(Area).filter(Area.name == "generale").first()
        if not area:
            area = Area(name="generale", description="General area")
            db_session.add(area)
            db_session.commit()

        return {"sender": sender, "recipient": recipient, "area": area}

    @pytest.mark.asyncio
    async def test_post_with_mention(self, db_session, setup_for_post):
        """Test that /post processes mentions."""
        from bbs.commands.dispatcher import CommandDispatcher

        dispatcher = CommandDispatcher(db_session)

        response = await dispatcher.dispatch(
            "/post Hey @Recipient check this out!",
            "sender12345678",
        )

        assert "pubblicato" in response
        assert "Recipient" in response  # Should show notified users

    @pytest.mark.asyncio
    async def test_inbox_shows_mentions(self, db_session, setup_for_post):
        """Test that /inbox shows mentions."""
        from bbs.commands.dispatcher import CommandDispatcher

        dispatcher = CommandDispatcher(db_session)

        # Create a mention
        notifier = get_mention_notifier()
        notifier.create_mention(
            recipient_key="recipient12345",
            sender_key="sender12345678",
            sender_name="Sender",
            message_id=1,
            area_name="generale",
            message_body="Hey @Recipient!",
        )

        # Check inbox
        response = await dispatcher.dispatch("/inbox", "recipient12345")

        assert "Menzioni" in response
        assert "@Sender" in response
        assert "/read 1" in response
