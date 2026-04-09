"""
Tests for /search command.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area


class TestSearchCommand:
    """Tests for /search command."""

    @pytest.mark.asyncio
    async def test_search_no_args(self, db_session: Session, test_sender_key: str):
        """Test /search without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search", test_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_search_query_too_short(self, db_session: Session, test_sender_key: str):
        """Test /search with too short query."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search a", test_sender_key)

        assert response is not None
        assert "troppo corto" in response.lower()

    @pytest.mark.asyncio
    async def test_search_no_results(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /search with no matching messages."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search xyznonexistent", test_sender_key)

        assert response is not None
        assert "nessun risultato" in response.lower()

    @pytest.mark.asyncio
    async def test_search_finds_messages(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /search finds matching messages."""
        # Create user and messages
        user = User(public_key=test_sender_key_2, nickname="Tester")
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg1 = Message(area_id=area.id, sender_key=test_sender_key_2, body="Hello world!")
        msg2 = Message(area_id=area.id, sender_key=test_sender_key_2, body="Another hello message")
        msg3 = Message(area_id=area.id, sender_key=test_sender_key_2, body="Goodbye world")
        db_session.add_all([msg1, msg2, msg3])
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search hello", test_sender_key)

        assert response is not None
        assert "2 risultati" in response.lower()
        assert "hello" in response.lower()

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search is case-insensitive."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="IMPORTANT MESSAGE")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search important", test_sender_key)

        assert response is not None
        assert "1 risultati" in response or "risultat" in response.lower()

    @pytest.mark.asyncio
    async def test_search_in_specific_area(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /search #area restricts to that area."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        generale = next(a for a in sample_areas if a.name == "generale")
        tech = next(a for a in sample_areas if a.name == "tech")

        # Create messages in different areas
        msg1 = Message(area_id=generale.id, sender_key=test_sender_key_2, body="Python is great")
        msg2 = Message(area_id=tech.id, sender_key=test_sender_key_2, body="Python tutorial")
        db_session.add_all([msg1, msg2])
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Search in tech only
        response = await dispatcher.dispatch("/search #tech python", test_sender_key)

        assert response is not None
        assert "1 risultati" in response or "risultat" in response.lower()
        assert "#tech" in response.lower()

    @pytest.mark.asyncio
    async def test_search_invalid_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test /search with non-existent area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search #nonexistent test", test_sender_key)

        assert response is not None
        assert "non trovata" in response.lower()

    @pytest.mark.asyncio
    async def test_search_shows_author(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search results show author name."""
        user = User(public_key=test_sender_key_2, nickname="AuthorNick")
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="Searchable content here")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search searchable", test_sender_key)

        assert response is not None
        assert "AuthorNick" in response

    @pytest.mark.asyncio
    async def test_search_shows_message_id(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search results show message ID."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="Find this message")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search find", test_sender_key)

        assert response is not None
        assert f"#{msg.id}" in response

    @pytest.mark.asyncio
    async def test_search_shows_area_name(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search results show area name."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        tech = next(a for a in sample_areas if a.name == "tech")
        msg = Message(area_id=tech.id, sender_key=test_sender_key_2, body="Technical stuff")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search technical", test_sender_key)

        assert response is not None
        assert "[tech]" in response.lower()

    @pytest.mark.asyncio
    async def test_search_shows_read_hint(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search results show hint to use /read."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="Test message content")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search test", test_sender_key)

        assert response is not None
        assert "/read" in response.lower()

    @pytest.mark.asyncio
    async def test_search_alias_find(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /find alias works."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="Alias test message")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/find alias", test_sender_key)

        assert response is not None
        assert "risultat" in response.lower()

    @pytest.mark.asyncio
    async def test_search_alias_s(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /s alias works."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="Short alias test")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/s short", test_sender_key)

        assert response is not None
        assert "risultat" in response.lower()

    @pytest.mark.asyncio
    async def test_search_multi_word_query(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test search with multi-word query."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body="The quick brown fox jumps")
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search quick brown", test_sender_key)

        assert response is not None
        # Should find the message with "quick brown" in it
        assert "risultat" in response.lower() or "nessun" in response.lower()

    @pytest.mark.asyncio
    async def test_search_preview_truncation(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test long messages are truncated in results."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        long_body = "This is a very long message " * 10 + "FINDME " + "more text " * 10
        msg = Message(area_id=area.id, sender_key=test_sender_key_2, body=long_body)
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search FINDME", test_sender_key)

        assert response is not None
        assert "risultat" in response.lower()
        # Response should be reasonably short (truncated)
        assert len(response) < 500


class TestSearchNoResultsMessages:
    """Tests for search result messages."""

    @pytest.mark.asyncio
    async def test_no_results_in_area(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test no results message mentions area."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search #tech xyznotfound", test_sender_key)

        assert response is not None
        assert "nessun risultato" in response.lower()
        assert "#tech" in response.lower()

    @pytest.mark.asyncio
    async def test_no_results_global(
        self, db_session: Session, test_sender_key: str, sample_areas: list[Area]
    ):
        """Test no results message for global search."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/search xyznotfound", test_sender_key)

        assert response is not None
        assert "nessun risultato" in response.lower()
        assert "xyznotfound" in response.lower()
