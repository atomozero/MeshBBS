"""
Tests for MeshCore connection module.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from datetime import datetime

from meshcore.connection import MockMeshCoreConnection, Identity
from meshcore.messages import Message, Advert
from meshcore.protocol import NodeType, PacketType


class TestIdentity:
    """Tests for Identity class."""

    def test_identity_creation(self):
        """Test creating an identity."""
        identity = Identity(
            public_key="A" * 64,
            name="TestNode",
            node_type=NodeType.ROOM,
        )

        assert identity.public_key == "A" * 64
        assert identity.name == "TestNode"
        assert identity.node_type == NodeType.ROOM

    def test_identity_short_key(self):
        """Test short_key property."""
        identity = Identity(public_key="ABCD1234" + "0" * 56, name="Test")
        assert identity.short_key == "ABCD1234"


class TestMockConnection:
    """Tests for MockMeshCoreConnection."""

    @pytest.mark.asyncio
    async def test_connect(self, mock_connection: MockMeshCoreConnection):
        """Test mock connection establishment."""
        assert not mock_connection.connected

        result = await mock_connection.connect()

        assert result is True
        assert mock_connection.connected
        assert mock_connection.identity is not None

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_connection: MockMeshCoreConnection):
        """Test mock disconnection."""
        await mock_connection.connect()
        assert mock_connection.connected

        await mock_connection.disconnect()

        assert not mock_connection.connected

    @pytest.mark.asyncio
    async def test_send_message(self, mock_connection: MockMeshCoreConnection):
        """Test sending a message."""
        await mock_connection.connect()

        result = await mock_connection.send_message(
            destination="B" * 64,
            text="Hello, mesh!",
        )

        assert result is True
        sent = mock_connection.get_sent_messages()
        assert len(sent) == 1
        assert sent[0].text == "Hello, mesh!"
        assert sent[0].recipient_key == "B" * 64

    @pytest.mark.asyncio
    async def test_send_message_not_connected(
        self, mock_connection: MockMeshCoreConnection
    ):
        """Test sending message when not connected."""
        result = await mock_connection.send_message(
            destination="B" * 64,
            text="Hello!",
        )

        assert result is False
        assert len(mock_connection.get_sent_messages()) == 0

    @pytest.mark.asyncio
    async def test_send_advert(self, mock_connection: MockMeshCoreConnection):
        """Test sending advertisement."""
        await mock_connection.connect()

        result = await mock_connection.send_advert(flood=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_receive_timeout(self, mock_connection: MockMeshCoreConnection):
        """Test receive with no messages (timeout)."""
        await mock_connection.connect()

        message = await mock_connection.receive()

        assert message is None

    @pytest.mark.asyncio
    async def test_inject_and_receive(self, mock_connection: MockMeshCoreConnection):
        """Test injecting and receiving a message."""
        await mock_connection.connect()

        # Inject a message
        await mock_connection.inject_message(
            sender_key="C" * 64,
            text="/help",
            hops=2,
            rssi=-85,
        )

        # Receive it
        message = await mock_connection.receive()

        assert message is not None
        assert message.sender_key == "C" * 64
        assert message.text == "/help"
        assert message.hops == 2
        assert message.rssi == -85

    @pytest.mark.asyncio
    async def test_clear_sent_messages(self, mock_connection: MockMeshCoreConnection):
        """Test clearing sent messages."""
        await mock_connection.connect()
        await mock_connection.send_message("B" * 64, "Test")

        assert len(mock_connection.get_sent_messages()) == 1

        mock_connection.clear_sent_messages()

        assert len(mock_connection.get_sent_messages()) == 0


class TestMessage:
    """Tests for Message dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = Message(
            sender_key="A" * 64,
            text="Hello!",
            recipient_key="B" * 64,
        )

        assert msg.sender_key == "A" * 64
        assert msg.text == "Hello!"
        assert msg.is_direct is True
        assert msg.timestamp is not None

    def test_message_is_direct(self):
        """Test is_direct property."""
        direct = Message(sender_key="A" * 64, text="Hi", recipient_key="B" * 64)
        broadcast = Message(sender_key="A" * 64, text="Hi")

        assert direct.is_direct is True
        assert broadcast.is_direct is False

    def test_message_sender_short(self):
        """Test sender_short property."""
        msg = Message(sender_key="ABCD1234" + "0" * 56, text="Hi")
        assert msg.sender_short == "ABCD1234"


class TestAdvert:
    """Tests for Advert dataclass."""

    def test_advert_creation(self):
        """Test creating an advert."""
        advert = Advert(
            public_key="A" * 64,
            name="TestBBS",
            node_type=NodeType.ROOM,
        )

        assert advert.name == "TestBBS"
        assert advert.node_type == NodeType.ROOM
        assert advert.has_location is False

    def test_advert_with_location(self):
        """Test advert with location."""
        advert = Advert(
            public_key="A" * 64,
            name="TestBBS",
            latitude=45.0,
            longitude=-93.0,
        )

        assert advert.has_location is True


class TestProtocol:
    """Tests for protocol definitions."""

    def test_packet_types(self):
        """Test packet type values."""
        assert PacketType.TXT_MSG == 0x02
        assert PacketType.ACK == 0x03
        assert PacketType.ADVERT == 0x04

    def test_node_types(self):
        """Test node type values."""
        assert NodeType.CHAT == 1
        assert NodeType.REPEATER == 2
        assert NodeType.ROOM == 3
        assert NodeType.SENSOR == 4
