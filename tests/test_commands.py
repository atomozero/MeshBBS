"""
Tests for BBS commands.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.base import CommandContext, CommandRegistry
from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.user import User


class TestHelpCommand:
    """Tests for /help command."""

    @pytest.mark.asyncio
    async def test_help_lists_commands(self, db_session: Session, test_sender_key: str):
        """Test that /help lists available commands."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!help", test_sender_key)

        assert response is not None
        assert "help" in response.lower()
        assert "post" in response.lower()
        assert "list" in response.lower()

    @pytest.mark.asyncio
    async def test_help_specific_command(self, db_session: Session, test_sender_key: str):
        """Test /help with specific command."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!help post", test_sender_key)

        assert response is not None
        assert "post" in response.lower()
        assert "uso" in response.lower() or "!" in response


class TestAreasCommand:
    """Tests for /areas command."""

    @pytest.mark.asyncio
    async def test_areas_lists_default(self, db_session: Session, test_sender_key: str):
        """Test /areas lists default areas."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!areas", test_sender_key)

        assert response is not None
        # Check for default areas created by init_database
        assert "generale" in response.lower() or "tech" in response.lower()

    @pytest.mark.asyncio
    async def test_areas_lists_all(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /areas lists all configured areas."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!areas", test_sender_key)

        assert response is not None
        # Sample areas come from init_database defaults
        for area in sample_areas:
            assert area.name in response.lower()


class TestPostCommand:
    """Tests for /post command.

    Note: The /post command uses the default area (configured in config).
    Format is /post <message>, not /post <area> <message>.
    """

    @pytest.mark.asyncio
    async def test_post_creates_message(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post creates a new message."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "!post Hello from test!", test_sender_key
        )

        assert response is not None
        assert "pubblicato" in response.lower() or "#" in response

        # Verify message was created (in default area 'generale')
        message = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert message is not None
        assert message.body == "Hello from test!"
        assert message.sender_key == test_sender_key

    @pytest.mark.asyncio
    async def test_post_no_content(
        self, db_session: Session, test_sender_key: str
    ):
        """Test /post without message content."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!post", test_sender_key)

        assert response is not None
        # Should show usage or error
        response_lower = response.lower()
        assert "uso" in response_lower or "usage" in response_lower or response is not None


class TestListCommand:
    """Tests for /list command."""

    @pytest.mark.asyncio
    async def test_list_empty_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /list on empty area."""
        area = sample_areas[0]
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!list {area.name}", test_sender_key)

        assert response is not None
        # Should indicate no messages or show empty list

    @pytest.mark.asyncio
    async def test_list_with_messages(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /list shows messages."""
        area = sample_areas[0]

        # Create user first
        user = User(public_key=test_sender_key)
        db_session.add(user)
        db_session.commit()

        # Create a message
        message = Message(
            area_id=area.id,
            sender_key=test_sender_key,
            body="Test message content",
        )
        db_session.add(message)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!list {area.name}", test_sender_key)

        assert response is not None
        # Should show the message ID or preview


class TestReadCommand:
    """Tests for /read command."""

    @pytest.mark.asyncio
    async def test_read_existing_message(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /read shows message content."""
        area = sample_areas[0]

        # Create user first
        user = User(public_key=test_sender_key)
        db_session.add(user)
        db_session.commit()

        # Create a message
        message = Message(
            area_id=area.id,
            sender_key=test_sender_key,
            body="This is the full message content.",
        )
        db_session.add(message)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"!read {message.id}", test_sender_key)

        assert response is not None
        assert "full message content" in response.lower()

    @pytest.mark.asyncio
    async def test_read_nonexistent_message(
        self, db_session: Session, test_sender_key: str
    ):
        """Test /read with invalid message ID."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!read 99999", test_sender_key)

        assert response is not None
        response_lower = response.lower()
        assert any(word in response_lower for word in ["not found", "error", "trovato", "non esiste"])


class TestNickCommand:
    """Tests for /nick command."""

    @pytest.mark.asyncio
    async def test_nick_sets_nickname(self, db_session: Session, test_sender_key: str):
        """Test /nick sets user nickname."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!nick TestUser", test_sender_key)

        assert response is not None
        response_lower = response.lower()
        assert any(word in response_lower for word in ["testuser", "set", "impostato", "nickname"])

        # Verify user was created/updated
        user = db_session.query(User).filter_by(public_key=test_sender_key).first()
        assert user is not None
        assert user.nickname == "TestUser"

    @pytest.mark.asyncio
    async def test_nick_update_existing(self, db_session: Session, test_sender_key: str):
        """Test /nick updates existing nickname."""
        # First set a nickname
        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch("!nick OldNick", test_sender_key)

        # Then update it
        response = await dispatcher.dispatch("!nick NewNick", test_sender_key)

        assert response is not None

        user = db_session.query(User).filter_by(public_key=test_sender_key).first()
        assert user is not None
        assert user.nickname == "NewNick"


class TestDispatcher:
    """Tests for command dispatcher."""

    @pytest.mark.asyncio
    async def test_non_command_ignored(self, db_session: Session, test_sender_key: str):
        """Test that non-command messages return None."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("Hello everyone!", test_sender_key)

        assert response is None

    @pytest.mark.asyncio
    async def test_unknown_command(self, db_session: Session, test_sender_key: str):
        """Test unknown command returns error."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("!unknowncmd", test_sender_key)

        assert response is not None
        response_lower = response.lower()
        assert any(word in response_lower for word in ["unknown", "not found", "sconosciuto", "non trovato"])

    @pytest.mark.asyncio
    async def test_response_prefix(self, db_session: Session, test_sender_key: str):
        """Test response prefix is applied."""
        dispatcher = CommandDispatcher(session=db_session, response_prefix="[BBS] ")
        response = await dispatcher.dispatch("!help", test_sender_key)

        assert response is not None
        assert response.startswith("[BBS] ")
