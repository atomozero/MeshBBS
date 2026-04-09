"""
Tests for Group Messages (GRP_TXT) support.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
from pathlib import Path
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshcore.messages import Message, GroupMessage
from meshcore.protocol import PacketType


class TestMessageGroupFields:
    """Test Message class group message fields."""

    def test_message_default_not_group(self):
        """Test that default message is not a group message."""
        msg = Message(
            sender_key="ABC123" + "0" * 58,
            text="Hello"
        )

        assert msg.is_group_message is False
        assert msg.channel_idx is None
        assert msg.is_channel is False

    def test_message_with_channel(self):
        """Test message with channel index."""
        msg = Message(
            sender_key="ABC123" + "0" * 58,
            text="Hello channel",
            channel_idx=5,
            is_group_message=True
        )

        assert msg.is_group_message is True
        assert msg.channel_idx == 5
        assert msg.is_channel is True

    def test_message_is_direct_not_group(self):
        """Test that direct message with recipient is not affected by group."""
        msg = Message(
            sender_key="ABC123" + "0" * 58,
            text="Private",
            recipient_key="DEF456" + "0" * 58,
            is_group_message=False
        )

        assert msg.is_direct is True
        assert msg.is_channel is False

    def test_message_is_not_direct_when_group(self):
        """Test that group message is not direct even with recipient."""
        msg = Message(
            sender_key="ABC123" + "0" * 58,
            text="Group message",
            recipient_key="DEF456" + "0" * 58,  # recipient ignored for groups
            is_group_message=True,
            channel_idx=3
        )

        assert msg.is_direct is False
        assert msg.is_channel is True

    def test_message_str_with_channel(self):
        """Test string representation includes channel."""
        msg = Message(
            sender_key="ABC123" + "0" * 58,
            text="Hello channel",
            channel_idx=2,
            is_group_message=True
        )

        str_repr = str(msg)
        assert "[CH2]" in str_repr
        assert "ABC12300" in str_repr


class TestGroupMessage:
    """Test GroupMessage class."""

    def test_group_message_creation(self):
        """Test creating a GroupMessage."""
        msg = GroupMessage(
            sender_key="ABC123" + "0" * 58,
            text="Group hello",
            channel_idx=1
        )

        assert msg.sender_key == "ABC123" + "0" * 58
        assert msg.text == "Group hello"
        assert msg.channel_idx == 1
        assert msg.timestamp is not None

    def test_group_message_metadata(self):
        """Test GroupMessage with network metadata."""
        msg = GroupMessage(
            sender_key="ABC123" + "0" * 58,
            text="Hello",
            channel_idx=5,
            hops=3,
            rssi=-85,
            snr=7.5
        )

        assert msg.hops == 3
        assert msg.rssi == -85
        assert msg.snr == 7.5

    def test_sender_short(self):
        """Test sender_short property."""
        msg = GroupMessage(
            sender_key="ABC123456789" + "0" * 52,
            text="Test",
            channel_idx=0
        )

        assert msg.sender_short == "ABC12345"

    def test_to_message_conversion(self):
        """Test converting GroupMessage to Message."""
        grp = GroupMessage(
            sender_key="ABC123" + "0" * 58,
            text="Group text",
            channel_idx=7,
            hops=2,
            rssi=-90,
            snr=5.0,
            message_id="msg123"
        )

        msg = grp.to_message()

        assert isinstance(msg, Message)
        assert msg.sender_key == grp.sender_key
        assert msg.text == grp.text
        assert msg.channel_idx == 7
        assert msg.is_group_message is True
        assert msg.hops == 2
        assert msg.rssi == -90
        assert msg.snr == 5.0
        assert msg.message_id == "msg123"

    def test_group_message_str(self):
        """Test GroupMessage string representation."""
        msg = GroupMessage(
            sender_key="ABC123" + "0" * 58,
            text="Hello world",
            channel_idx=4
        )

        str_repr = str(msg)
        assert "[CH4]" in str_repr
        assert "ABC12300" in str_repr
        assert "Hello world" in str_repr


class TestPacketTypeGRPTXT:
    """Test GRP_TXT packet type."""

    def test_grp_txt_defined(self):
        """Test that GRP_TXT is defined in PacketType."""
        assert hasattr(PacketType, 'GRP_TXT')
        assert PacketType.GRP_TXT == 0x05

    def test_grp_data_defined(self):
        """Test that GRP_DATA is defined."""
        assert hasattr(PacketType, 'GRP_DATA')
        assert PacketType.GRP_DATA == 0x06


class TestChannelMessageIntegration:
    """Integration tests for channel message handling."""

    def test_message_roundtrip(self):
        """Test creating and processing a channel message."""
        # Simulate receiving a group message
        original = GroupMessage(
            sender_key="SENDER" + "0" * 58,
            text="Channel announcement",
            channel_idx=3,
            hops=1,
            rssi=-70
        )

        # Convert to Message for processing
        msg = original.to_message()

        # Verify all data preserved
        assert msg.sender_key == original.sender_key
        assert msg.text == original.text
        assert msg.channel_idx == original.channel_idx
        assert msg.is_channel is True
        assert msg.hops == original.hops
        assert msg.rssi == original.rssi

    def test_channel_zero_valid(self):
        """Test that channel 0 is valid."""
        msg = GroupMessage(
            sender_key="ABC" + "0" * 61,
            text="Channel 0",
            channel_idx=0
        )

        assert msg.channel_idx == 0
        converted = msg.to_message()
        assert converted.is_channel is True

    def test_various_channels(self):
        """Test various channel indices."""
        channels = [0, 1, 5, 10, 15, 255]

        for ch in channels:
            msg = GroupMessage(
                sender_key="ABC" + "0" * 61,
                text=f"Channel {ch}",
                channel_idx=ch
            )
            assert msg.channel_idx == ch
            assert f"[CH{ch}]" in str(msg)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
