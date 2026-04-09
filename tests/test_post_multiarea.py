"""
Tests for /post command with multi-area support.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area


class TestPostMultiArea:
    """Tests for /post command with area specification."""

    @pytest.mark.asyncio
    async def test_post_default_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post without area uses default area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post Hello world!", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()
        assert "#" in response  # Has message ID

        # Verify message was created in default area (generale)
        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.body == "Hello world!"
        assert msg.area.name == "generale"

    @pytest.mark.asyncio
    async def test_post_with_hash_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post #area message syntax."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #tech Technical question", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()
        assert "#tech" in response.lower()

        # Verify message was created in tech area
        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.body == "Technical question"
        assert msg.area.name == "tech"

    @pytest.mark.asyncio
    async def test_post_with_area_name(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post areaname message syntax."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post tech Another tech post", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()

        # Verify message was created in tech area
        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.body == "Another tech post"
        assert msg.area.name == "tech"

    @pytest.mark.asyncio
    async def test_post_area_not_found(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post with non-existent area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #nonexistent Hello", test_sender_key)

        assert response is not None
        assert "non trovata" in response.lower()
        assert "aree disponibili" in response.lower()

    @pytest.mark.asyncio
    async def test_post_case_insensitive_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test area names are case-insensitive."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #TECH Uppercase area", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()

        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.area.name == "tech"

    @pytest.mark.asyncio
    async def test_post_readonly_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test cannot post to read-only area."""
        # Make emergenze area read-only
        emergenze = db_session.query(Area).filter_by(name="emergenze").first()
        if emergenze:
            emergenze.is_readonly = True
            db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #emergenze Emergency!", test_sender_key)

        assert response is not None
        assert "sola lettura" in response.lower()

    @pytest.mark.asyncio
    async def test_post_only_area_no_message(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /post #area without message text."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #tech", test_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_post_message_starting_with_hash(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test posting a message that starts with # (not an area)."""
        dispatcher = CommandDispatcher(session=db_session)
        # #hashtag is not a valid area, so entire message goes to default area
        response = await dispatcher.dispatch("/post #hashtag is cool", test_sender_key)

        # Should fail because #hashtag is not a valid area
        assert response is not None
        assert "non trovata" in response.lower()

    @pytest.mark.asyncio
    async def test_post_area_name_as_message(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test that area-like word alone is treated as message."""
        # If only one word and it's an area name, it could be ambiguous
        # Our implementation requires message after area, so this posts to default
        dispatcher = CommandDispatcher(session=db_session)
        # "tech" alone - no message after it, so "tech" IS the message
        response = await dispatcher.dispatch("/post tech", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()

        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        # "tech" should be the message body in default area
        assert msg.body == "tech"
        assert msg.area.name == "generale"

    @pytest.mark.asyncio
    async def test_post_shows_area_in_non_default(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test response includes area name when not default."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #tech Test message", test_sender_key)

        assert response is not None
        assert "#tech" in response.lower()

    @pytest.mark.asyncio
    async def test_post_hides_area_in_default(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test response doesn't show area when posting to default."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post Just a message", test_sender_key)

        assert response is not None
        assert "pubblicato" in response.lower()
        # Should not mention area name for default
        assert "#generale" not in response.lower() or "pubblicato in" not in response.lower()

    @pytest.mark.asyncio
    async def test_post_preserves_message_with_multiple_spaces(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test message preserves multiple words."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            "/post #tech This is a longer message with multiple words", test_sender_key
        )

        assert response is not None
        assert "pubblicato" in response.lower()

        msg = db_session.query(Message).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.body == "This is a longer message with multiple words"

    @pytest.mark.asyncio
    async def test_post_aliases_with_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /p and /say aliases work with area."""
        dispatcher = CommandDispatcher(session=db_session)

        # Test /p
        response = await dispatcher.dispatch("/p #tech Short post", test_sender_key)
        assert "pubblicato" in response.lower()

        # Clean up for next test
        db_session.query(Message).filter_by(sender_key=test_sender_key).delete()
        db_session.commit()

        # Test /say
        response = await dispatcher.dispatch("/say #tech Say something", test_sender_key)
        assert "pubblicato" in response.lower()


class TestPostUsageHelp:
    """Tests for /post usage and help messages."""

    @pytest.mark.asyncio
    async def test_post_no_args_shows_examples(
        self, db_session: Session, test_sender_key: str
    ):
        """Test /post with no args shows usage with examples."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post", test_sender_key)

        assert response is not None
        assert "uso" in response.lower()
        assert "#area" in response.lower() or "esempio" in response.lower()

    @pytest.mark.asyncio
    async def test_post_invalid_area_lists_available(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test invalid area shows list of available areas."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/post #invalid Test", test_sender_key)

        assert response is not None
        assert "non trovata" in response.lower()
        # Should list available areas
        assert "generale" in response.lower() or "tech" in response.lower()
