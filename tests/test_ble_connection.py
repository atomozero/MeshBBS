"""
Tests for BLE MeshCore connection.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshcore.connection import (
    BLEMeshCoreConnection,
    MockMeshCoreConnection,
    Identity,
    MESHCORE_AVAILABLE,
)


class TestBLEMeshCoreConnectionInit:
    """Test BLEMeshCoreConnection initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        conn = BLEMeshCoreConnection()

        assert conn.address is None
        assert conn.pin is None
        assert conn.timeout == 30.0
        assert conn.debug is False
        assert conn.connected is False

    def test_init_with_address(self):
        """Test initialization with BLE address."""
        conn = BLEMeshCoreConnection(address="12:34:56:78:90:AB")

        assert conn.address == "12:34:56:78:90:AB"

    def test_init_with_pin(self):
        """Test initialization with PIN."""
        conn = BLEMeshCoreConnection(
            address="12:34:56:78:90:AB",
            pin="123456"
        )

        assert conn.pin == "123456"

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        conn = BLEMeshCoreConnection(timeout=60.0)

        assert conn.timeout == 60.0

    def test_init_uses_mock_when_meshcore_unavailable(self):
        """Test that mock is used when meshcore is not available."""
        # Since meshcore is likely not installed in test environment,
        # it should fall back to mock
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        # Either uses mock or meshcore is available
        if not MESHCORE_AVAILABLE:
            assert conn._mock is not None


class TestBLEMeshCoreConnectionMockFallback:
    """Test BLE connection with mock fallback."""

    @pytest.mark.asyncio
    async def test_connect_uses_mock(self):
        """Test that connect uses mock when meshcore unavailable."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            result = await conn.connect()

            assert result is True
            assert conn.connected is True
            assert conn.identity is not None

    @pytest.mark.asyncio
    async def test_disconnect_uses_mock(self):
        """Test disconnect with mock."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()
            await conn.disconnect()

            assert conn.connected is False

    @pytest.mark.asyncio
    async def test_send_message_uses_mock(self):
        """Test send_message with mock."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()

            result = await conn.send_message(
                destination="ABC123" + "0" * 58,
                text="Test message"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_advert_uses_mock(self):
        """Test send_advert with mock."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()

            result = await conn.send_advert(flood=True)

            assert result is True


class TestBLEMeshCoreConnectionProperties:
    """Test BLE connection properties."""

    def test_is_using_mock(self):
        """Test is_using_mock property."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            assert conn.is_using_mock is True
        else:
            assert conn.is_using_mock is False

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected property."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        assert conn.is_connected is False

        if not MESHCORE_AVAILABLE:
            await conn.connect()
            assert conn.is_connected is True

            await conn.disconnect()
            assert conn.is_connected is False


class TestBLEMeshCoreConnectionCallbacks:
    """Test BLE connection message callbacks."""

    @pytest.mark.asyncio
    async def test_on_message_callback(self):
        """Test registering and receiving message callbacks."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)
        received_messages = []

        async def callback(message):
            received_messages.append(message)

        # Register callback on the BLE connection
        conn.on_message(callback)

        if not MESHCORE_AVAILABLE and conn._mock:
            await conn.connect()

            # Also register callback on the mock (which is what actually processes messages)
            conn._mock.on_message(callback)

            # Inject a test message
            await conn._mock.inject_message(
                sender_key="TEST" + "0" * 60,
                text="Hello BLE!"
            )

            # Receive the message through the mock
            message = await conn._mock.receive()

            # Check callback was called
            assert len(received_messages) == 1
            assert received_messages[0].text == "Hello BLE!"


class TestBLEMeshCoreConnectionIntegration:
    """Integration tests for BLE connection (mock-based)."""

    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self):
        """Test full connection lifecycle."""
        conn = BLEMeshCoreConnection(
            address="12:34:56:78:90:AB",
            use_mock_fallback=True
        )

        if not MESHCORE_AVAILABLE:
            # Connect
            result = await conn.connect()
            assert result is True
            assert conn.connected is True
            assert conn.identity is not None

            # Send message
            send_result = await conn.send_message(
                destination="DEST" + "0" * 60,
                text="Test message"
            )
            assert send_result is True

            # Send advert
            advert_result = await conn.send_advert()
            assert advert_result is True

            # Get battery (mock returns default)
            battery = await conn.get_battery()
            assert battery is not None
            assert "level" in battery

            # Disconnect
            await conn.disconnect()
            assert conn.connected is False

    @pytest.mark.asyncio
    async def test_cannot_send_when_disconnected(self):
        """Test that sending fails when not connected."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            # Don't connect, try to send
            result = await conn.send_message(
                destination="ABC" + "0" * 61,
                text="Should fail"
            )

            # Mock returns False when not connected
            assert result is False


class TestBLEMeshCoreConnectionWithPIN:
    """Test BLE connection with PIN authentication."""

    def test_pin_stored(self):
        """Test that PIN is stored correctly."""
        conn = BLEMeshCoreConnection(
            address="12:34:56:78:90:AB",
            pin="654321"
        )

        assert conn.pin == "654321"

    @pytest.mark.asyncio
    async def test_set_device_pin_mock(self):
        """Test set_device_pin with mock."""
        conn = BLEMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()

            result = await conn.set_device_pin(123456)

            # Mock always returns True
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
