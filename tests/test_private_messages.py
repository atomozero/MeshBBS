"""
Tests for private messaging system (/msg, /inbox, /readpm).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from sqlalchemy.orm import Session

from bbs.commands.dispatcher import CommandDispatcher
from bbs.models.user import User
from bbs.models.private_message import PrivateMessage
from bbs.repositories.private_message_repository import PrivateMessageRepository


class TestMsgCommand:
    """Tests for /msg command."""

    @pytest.mark.asyncio
    async def test_msg_no_args(self, db_session: Session, test_sender_key: str):
        """Test /msg without arguments shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg", test_sender_key)

        assert response is not None
        assert "uso" in response.lower() or "usage" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_no_message(self, db_session: Session, test_sender_key: str):
        """Test /msg with only recipient shows usage."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg someone", test_sender_key)

        assert response is not None
        assert "uso" in response.lower() or "usage" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_user_not_found(self, db_session: Session, test_sender_key: str):
        """Test /msg to non-existent user."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg nonexistent Hello!", test_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_send_by_nickname(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test sending message by nickname."""
        # Create recipient with nickname
        recipient = User(public_key=test_sender_key_2, nickname="Mario")
        db_session.add(recipient)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg Mario Ciao come stai?", test_sender_key)

        assert response is not None
        assert "inviato" in response.lower()
        assert "Mario" in response

        # Verify message was created
        msg = db_session.query(PrivateMessage).filter_by(sender_key=test_sender_key).first()
        assert msg is not None
        assert msg.body == "Ciao come stai?"
        assert msg.recipient_key == test_sender_key_2

    @pytest.mark.asyncio
    async def test_msg_send_by_public_key(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test sending message by public key prefix."""
        # Create recipient
        recipient = User(public_key=test_sender_key_2)
        db_session.add(recipient)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        # Use first 8 chars of key
        response = await dispatcher.dispatch(
            f"/msg {test_sender_key_2[:8]} Hello there!", test_sender_key
        )

        assert response is not None
        assert "inviato" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_cannot_send_to_self(
        self, db_session: Session, test_sender_key: str
    ):
        """Test cannot send message to yourself."""
        # Create sender user with nickname
        user = User(public_key=test_sender_key, nickname="Myself")
        db_session.add(user)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg Myself Hello me!", test_sender_key)

        assert response is not None
        assert "te stesso" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_cannot_send_to_banned(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot send message to banned user."""
        # Create banned recipient
        recipient = User(public_key=test_sender_key_2, nickname="Banned", is_banned=True)
        db_session.add(recipient)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/msg Banned Hello!", test_sender_key)

        assert response is not None
        assert "impossibile" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_too_long(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test message length limit."""
        recipient = User(public_key=test_sender_key_2, nickname="Mario")
        db_session.add(recipient)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        long_message = "x" * 250
        response = await dispatcher.dispatch(f"/msg Mario {long_message}", test_sender_key)

        assert response is not None
        assert "troppo lungo" in response.lower()

    @pytest.mark.asyncio
    async def test_msg_aliases(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /pm, /dm, /tell aliases work."""
        recipient = User(public_key=test_sender_key_2, nickname="Mario")
        db_session.add(recipient)
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        # Test /pm
        response = await dispatcher.dispatch("/pm Mario Test 1", test_sender_key)
        assert "inviato" in response.lower()

        # Test /dm
        response = await dispatcher.dispatch("/dm Mario Test 2", test_sender_key)
        assert "inviato" in response.lower()

        # Test /tell
        response = await dispatcher.dispatch("/tell Mario Test 3", test_sender_key)
        assert "inviato" in response.lower()


class TestInboxCommand:
    """Tests for /inbox command."""

    @pytest.mark.asyncio
    async def test_inbox_empty(self, db_session: Session, test_sender_key: str):
        """Test /inbox with no messages."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/inbox", test_sender_key)

        assert response is not None
        assert "nessun" in response.lower()

    @pytest.mark.asyncio
    async def test_inbox_with_messages(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /inbox shows received messages."""
        # Create sender
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        db_session.add(sender)

        # Create recipient
        recipient = User(public_key=test_sender_key)
        db_session.add(recipient)
        db_session.commit()

        # Send a message
        pm_repo = PrivateMessageRepository(db_session)
        pm_repo.send_message(
            sender_key=test_sender_key_2,
            recipient_key=test_sender_key,
            body="Hello from sender!"
        )
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/inbox", test_sender_key)

        assert response is not None
        assert "Sender" in response
        assert "Hello" in response or "#" in response

    @pytest.mark.asyncio
    async def test_inbox_shows_unread_count(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /inbox shows unread count."""
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 1")
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 2")
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/inbox", test_sender_key)

        assert response is not None
        assert "2" in response  # 2 unread

    @pytest.mark.asyncio
    async def test_inbox_with_limit(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /inbox with custom limit."""
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        for i in range(5):
            pm_repo.send_message(test_sender_key_2, test_sender_key, f"Msg {i}")
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/inbox 2", test_sender_key)

        assert response is not None
        # Should show only 2 messages

    @pytest.mark.asyncio
    async def test_inbox_invalid_limit(self, db_session: Session, test_sender_key: str):
        """Test /inbox with invalid limit."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/inbox abc", test_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_inbox_aliases(self, db_session: Session, test_sender_key: str):
        """Test /mail, /pms aliases work."""
        dispatcher = CommandDispatcher(session=db_session)

        response = await dispatcher.dispatch("/mail", test_sender_key)
        assert response is not None

        response = await dispatcher.dispatch("/pms", test_sender_key)
        assert response is not None


class TestReadPmCommand:
    """Tests for /readpm command."""

    @pytest.mark.asyncio
    async def test_readpm_no_args(self, db_session: Session, test_sender_key: str):
        """Test /readpm without arguments."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/readpm", test_sender_key)

        assert response is not None
        assert "uso" in response.lower()

    @pytest.mark.asyncio
    async def test_readpm_invalid_id(self, db_session: Session, test_sender_key: str):
        """Test /readpm with invalid ID."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/readpm abc", test_sender_key)

        assert response is not None
        assert "non valido" in response.lower()

    @pytest.mark.asyncio
    async def test_readpm_not_found(self, db_session: Session, test_sender_key: str):
        """Test /readpm with non-existent message."""
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch("/readpm 99999", test_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_readpm_as_recipient(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test reading a message as recipient."""
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        msg = pm_repo.send_message(
            test_sender_key_2, test_sender_key, "Secret message content"
        )
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/readpm {msg.id}", test_sender_key)

        assert response is not None
        assert "Secret message content" in response
        assert "Da: Sender" in response

    @pytest.mark.asyncio
    async def test_readpm_as_sender(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test reading a message as sender."""
        sender = User(public_key=test_sender_key)
        recipient = User(public_key=test_sender_key_2, nickname="Recipient")
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        msg = pm_repo.send_message(
            test_sender_key, test_sender_key_2, "My sent message"
        )
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/readpm {msg.id}", test_sender_key)

        assert response is not None
        assert "My sent message" in response
        assert "A: Recipient" in response

    @pytest.mark.asyncio
    async def test_readpm_marks_as_read(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test reading a message marks it as read."""
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        msg = pm_repo.send_message(test_sender_key_2, test_sender_key, "Unread message")
        db_session.commit()

        # Verify initially unread
        assert not msg.is_read

        dispatcher = CommandDispatcher(session=db_session)
        await dispatcher.dispatch(f"/readpm {msg.id}", test_sender_key)

        # Refresh from DB
        db_session.refresh(msg)
        assert msg.is_read

    @pytest.mark.asyncio
    async def test_readpm_unauthorized(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test cannot read other people's messages."""
        sender = User(public_key=test_sender_key_2)
        recipient = User(public_key="C" * 64)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        msg = pm_repo.send_message(test_sender_key_2, "C" * 64, "Private to others")
        db_session.commit()

        # Try to read as third party
        dispatcher = CommandDispatcher(session=db_session)
        response = await dispatcher.dispatch(f"/readpm {msg.id}", test_sender_key)

        assert response is not None
        assert "non trovato" in response.lower()

    @pytest.mark.asyncio
    async def test_readpm_aliases(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test /rpm, /viewpm aliases work."""
        sender = User(public_key=test_sender_key_2, nickname="Sender")
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        msg = pm_repo.send_message(test_sender_key_2, test_sender_key, "Test")
        db_session.commit()

        dispatcher = CommandDispatcher(session=db_session)

        response = await dispatcher.dispatch(f"/rpm {msg.id}", test_sender_key)
        assert "Test" in response

        response = await dispatcher.dispatch(f"/viewpm {msg.id}", test_sender_key)
        assert "Test" in response


class TestPrivateMessageRepository:
    """Tests for PrivateMessageRepository."""

    def test_get_unread_count(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test unread count calculation."""
        sender = User(public_key=test_sender_key_2)
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)

        # Initially 0
        assert pm_repo.get_unread_count(test_sender_key) == 0

        # Add messages
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 1")
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 2")
        db_session.commit()

        # Now 2 unread
        assert pm_repo.get_unread_count(test_sender_key) == 2

    def test_get_conversation(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test getting conversation between two users."""
        user1 = User(public_key=test_sender_key)
        user2 = User(public_key=test_sender_key_2)
        db_session.add_all([user1, user2])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)

        # Exchange messages
        pm_repo.send_message(test_sender_key, test_sender_key_2, "Hello")
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Hi back")
        pm_repo.send_message(test_sender_key, test_sender_key_2, "How are you?")
        db_session.commit()

        # Get conversation
        conv = pm_repo.get_conversation(test_sender_key, test_sender_key_2)
        assert len(conv) == 3

    def test_mark_conversation_as_read(
        self, db_session: Session, test_sender_key: str, test_sender_key_2: str
    ):
        """Test marking all messages from a user as read."""
        sender = User(public_key=test_sender_key_2)
        recipient = User(public_key=test_sender_key)
        db_session.add_all([sender, recipient])
        db_session.commit()

        pm_repo = PrivateMessageRepository(db_session)
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 1")
        pm_repo.send_message(test_sender_key_2, test_sender_key, "Msg 2")
        db_session.commit()

        # Mark all as read
        count = pm_repo.mark_conversation_as_read(test_sender_key, test_sender_key_2)
        assert count == 2

        # Verify all read
        assert pm_repo.get_unread_count(test_sender_key) == 0
