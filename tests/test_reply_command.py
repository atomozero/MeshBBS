"""
Tests for /reply command (message threading).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.repositories.message_repository import MessageRepository


class TestReplyCommand:
    """Tests for /reply command."""

    @pytest.mark.asyncio
    async def test_reply_no_args(self, db_session: Session, test_sender_key: str):
        """Test /reply without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/reply", test_sender_key)

        assert response is not None
        assert "uso" in response.lower() or "/reply" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_no_message(self, db_session: Session, test_sender_key: str):
        """Test /reply with only ID shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/reply 1", test_sender_key)

        assert response is not None
        assert "uso" in response.lower() or "/reply" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_invalid_id(self, db_session: Session, test_sender_key: str):
        """Test /reply with invalid ID."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/reply abc Hello", test_sender_key)

        assert response is not None
        assert "non valido" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_message_not_found(self, db_session: Session, test_sender_key: str):
        """Test /reply to non-existent message."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/reply 99999 Hello", test_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_success(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test successful reply to a message."""
        # Create original author
        author = User(public_key=test_sender_key_2, nickname="Author")
        db_session.add(author)
        db_session.commit()

        # Create original message
        area = sample_areas[0]
        original_msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original message content"
        )
        db_session.add(original_msg)
        db_session.commit()

        # Reply to the message
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            f"/reply {original_msg.id} I agree with you!", test_sender_key
        )

        assert response is not None
        assert "risposta" in response.lower()
        assert f"#{original_msg.id}" in response

        # Verify reply was created
        reply = (
            db_session.query(Message)
            .filter(Message.parent_id == original_msg.id)
            .first()
        )
        assert reply is not None
        assert reply.body == "I agree with you!"
        assert reply.sender_key == test_sender_key
        assert reply.area_id == area.id

    @pytest.mark.asyncio
    async def test_reply_with_hash_prefix(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test reply with # prefix in ID."""
        author = User(public_key=test_sender_key_2)
        db_session.add(author)
        db_session.commit()

        area = sample_areas[0]
        original_msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original message"
        )
        db_session.add(original_msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            f"/reply #{original_msg.id} Reply text", test_sender_key
        )

        assert response is not None
        assert "risposta" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_too_long(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test reply with too long message."""
        author = User(public_key=test_sender_key_2)
        db_session.add(author)
        db_session.commit()

        area = sample_areas[0]
        original_msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original"
        )
        db_session.add(original_msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        long_reply = "x" * 250
        response = await dispatcher.dispatch(
            f"/reply {original_msg.id} {long_reply}", test_sender_key
        )

        assert response is not None
        assert "troppo lungo" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_inherits_area(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test that reply is created in same area as parent."""
        author = User(public_key=test_sender_key_2)
        db_session.add(author)
        db_session.commit()

        # Use tech area (not default)
        tech_area = next((a for a in sample_areas if a.name == "tech"), sample_areas[1])
        original_msg = Message(
            area_id=tech_area.id,
            sender_key=test_sender_key_2,
            body="Tech discussion"
        )
        db_session.add(original_msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch(
            f"/reply {original_msg.id} Tech reply", test_sender_key
        )

        # Verify reply is in tech area
        reply = (
            db_session.query(Message)
            .filter(Message.parent_id == original_msg.id)
            .first()
        )
        assert reply is not None
        assert reply.area_id == tech_area.id

    @pytest.mark.asyncio
    async def test_reply_alias_re(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /re alias works."""
        author = User(public_key=test_sender_key_2)
        db_session.add(author)
        db_session.commit()

        area = sample_areas[0]
        original_msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original"
        )
        db_session.add(original_msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            f"/re {original_msg.id} Short reply", test_sender_key
        )

        assert response is not None
        assert "risposta" in response.lower()

    @pytest.mark.asyncio
    async def test_reply_shows_parent_author(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test reply response shows parent author."""
        author = User(public_key=test_sender_key_2, nickname="OrigAuthor")
        db_session.add(author)
        db_session.commit()

        area = sample_areas[0]
        original_msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original"
        )
        db_session.add(original_msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(
            f"/reply {original_msg.id} My reply", test_sender_key
        )

        assert response is not None
        assert "OrigAuthor" in response

    @pytest.mark.asyncio
    async def test_nested_replies(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test nested replies (reply to a reply)."""
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        area = sample_areas[0]

        # Original message
        original = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Original post"
        )
        db_session.add(original)
        db_session.commit()

        # First reply
        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch(
            f"/reply {original.id} First reply", test_sender_key
        )
        db_session.commit()

        first_reply = (
            db_session.query(Message)
            .filter(Message.parent_id == original.id)
            .first()
        )
        assert first_reply is not None

        # Reply to the reply
        response = await dispatcher.dispatch(
            f"/reply {first_reply.id} Nested reply", test_sender_key_2
        )
        db_session.commit()

        assert response is not None
        assert "risposta" in response.lower()

        # Verify nested reply
        nested = (
            db_session.query(Message)
            .filter(Message.parent_id == first_reply.id)
            .first()
        )
        assert nested is not None
        assert nested.body == "Nested reply"


class TestReadCommandWithReplies:
    """Tests for /read command with threading features."""

    @pytest.mark.asyncio
    async def test_read_shows_reply_count(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /read shows reply count."""
        # Create both users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        area = sample_areas[0]
        original = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Post with replies"
        )
        db_session.add(original)
        db_session.commit()

        # Add replies
        for i in range(3):
            reply = Message(
                area_id=area.id,
                sender_key=test_sender_key,
                body=f"Reply {i}",
                parent_id=original.id
            )
            db_session.add(reply)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/read {original.id}", test_sender_key)

        assert response is not None
        assert "3 risposte" in response

    @pytest.mark.asyncio
    async def test_read_shows_parent_info(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /read shows parent message info for replies."""
        # Create both users first
        user1 = User(public_key=test_sender_key)
        author = User(public_key=test_sender_key_2, nickname="ParentAuthor")
        db_session.add_all([user1, author])
        db_session.commit()

        area = sample_areas[0]
        parent = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="Parent message"
        )
        db_session.add(parent)
        db_session.commit()

        reply = Message(
            area_id=area.id,
            sender_key=test_sender_key,
            body="Reply message",
            parent_id=parent.id
        )
        db_session.add(reply)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/read {reply.id}", test_sender_key)

        assert response is not None
        assert f"re: #{parent.id}" in response.lower() or "parentauthor" in response.lower()

    @pytest.mark.asyncio
    async def test_read_shows_reply_hint(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test /read shows reply hint."""
        user = User(public_key=test_sender_key_2)
        db_session.add(user)
        db_session.commit()

        area = sample_areas[0]
        msg = Message(
            area_id=area.id,
            sender_key=test_sender_key_2,
            body="A message"
        )
        db_session.add(msg)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/read {msg.id}", test_sender_key)

        assert response is not None
        assert f"/reply {msg.id}" in response


class TestMessageThreading:
    """Tests for message threading functionality."""

    def test_message_is_reply_property(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test is_reply property."""
        # Create users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        area = sample_areas[0]

        parent = Message(area_id=area.id, sender_key=test_sender_key, body="Parent")
        db_session.add(parent)
        db_session.commit()

        assert not parent.is_reply

        child = Message(area_id=area.id, sender_key=test_sender_key_2, body="Child", parent_id=parent.id)
        db_session.add(child)
        db_session.commit()

        assert child.is_reply

    def test_message_reply_count(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test reply_count property."""
        # Create users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        area = sample_areas[0]

        parent = Message(area_id=area.id, sender_key=test_sender_key, body="Parent")
        db_session.add(parent)
        db_session.commit()

        assert parent.reply_count == 0

        # Add replies
        for i in range(5):
            child = Message(
                area_id=area.id,
                sender_key=test_sender_key_2,
                body=f"Reply {i}",
                parent_id=parent.id
            )
            db_session.add(child)
        db_session.commit()

        db_session.refresh(parent)
        assert parent.reply_count == 5

    def test_get_thread(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str, sample_areas: list[Area]
    ):
        """Test get_thread method."""
        # Create users first
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        user3_key = "C" * 64
        user4_key = "D" * 64
        user3 = User(public_key=user3_key)
        user4 = User(public_key=user4_key)
        db_session.add_all([user1, user2, user3, user4])
        db_session.commit()

        area = sample_areas[0]

        # Create thread: parent -> reply1, reply2 -> nested
        parent = Message(area_id=area.id, sender_key=test_sender_key, body="Parent")
        db_session.add(parent)
        db_session.commit()

        reply1 = Message(area_id=area.id, sender_key=test_sender_key_2, body="Reply 1", parent_id=parent.id)
        reply2 = Message(area_id=area.id, sender_key=user3_key, body="Reply 2", parent_id=parent.id)
        db_session.add_all([reply1, reply2])
        db_session.commit()

        nested = Message(area_id=area.id, sender_key=user4_key, body="Nested", parent_id=reply1.id)
        db_session.add(nested)
        db_session.commit()

        # Get thread from any message
        thread = parent.get_thread()
        assert len(thread) == 4

        # Thread from nested should include all
        db_session.refresh(nested)
        thread_from_nested = nested.get_thread()
        assert len(thread_from_nested) == 4
