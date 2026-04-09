"""
Tests for TCP MeshCore connection.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import pytest
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshcore.connection import (
    TCPMeshCoreConnection,
    MockMeshCoreConnection,
    MESHCORE_AVAILABLE,
)


class TestTCPMeshCoreConnectionInit:
    """Test TCPMeshCoreConnection initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        conn = TCPMeshCoreConnection()

        assert conn.host == "192.168.1.100"
        assert conn.port == 4403
        assert conn.timeout == 30.0
        assert conn.debug is False
        assert conn.connected is False

    def test_init_with_custom_host(self):
        """Test initialization with custom host."""
        conn = TCPMeshCoreConnection(host="10.0.0.1")

        assert conn.host == "10.0.0.1"

    def test_init_with_custom_port(self):
        """Test initialization with custom port."""
        conn = TCPMeshCoreConnection(port=5000)

        assert conn.port == 5000

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        conn = TCPMeshCoreConnection(timeout=60.0)

        assert conn.timeout == 60.0

    def test_init_uses_mock_when_meshcore_unavailable(self):
        """Test that mock is used when meshcore is not available."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            assert conn._mock is not None

    def test_endpoint_property(self):
        """Test the endpoint property."""
        conn = TCPMeshCoreConnection(host="192.168.1.50", port=4000)

        assert conn.endpoint == "192.168.1.50:4000"


class TestTCPMeshCoreConnectionMockFallback:
    """Test TCP connection with mock fallback."""

    @pytest.mark.asyncio
    async def test_connect_uses_mock(self):
        """Test that connect uses mock when meshcore unavailable."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            result = await conn.connect()

            assert result is True
            assert conn.connected is True
            assert conn.identity is not None

    @pytest.mark.asyncio
    async def test_disconnect_uses_mock(self):
        """Test disconnect with mock."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()
            await conn.disconnect()

            assert conn.connected is False

    @pytest.mark.asyncio
    async def test_send_message_uses_mock(self):
        """Test send_message with mock."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

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
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            await conn.connect()

            result = await conn.send_advert(flood=True)

            assert result is True


class TestTCPMeshCoreConnectionProperties:
    """Test TCP connection properties."""

    def test_is_using_mock(self):
        """Test is_using_mock property."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            assert conn.is_using_mock is True
        else:
            assert conn.is_using_mock is False

    @pytest.mark.asyncio
    async def test_is_connected(self):
        """Test is_connected property."""
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        assert conn.is_connected is False

        if not MESHCORE_AVAILABLE:
            await conn.connect()
            assert conn.is_connected is True

            await conn.disconnect()
            assert conn.is_connected is False


class TestTCPMeshCoreConnectionIntegration:
    """Integration tests for TCP connection (mock-based)."""

    @pytest.mark.asyncio
    async def test_full_connection_lifecycle(self):
        """Test full connection lifecycle."""
        conn = TCPMeshCoreConnection(
            host="192.168.1.100",
            port=4403,
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
        conn = TCPMeshCoreConnection(use_mock_fallback=True)

        if not MESHCORE_AVAILABLE:
            # Don't connect, try to send
            result = await conn.send_message(
                destination="ABC" + "0" * 61,
                text="Should fail"
            )

            # Mock returns False when not connected
            assert result is False


class TestTCPMeshCoreConnectionDifferentPorts:
    """Test TCP connection with different port configurations."""

    def test_common_ports(self):
        """Test common port values."""
        ports = [4000, 4403, 5000, 8080]

        for port in ports:
            conn = TCPMeshCoreConnection(port=port)
            assert conn.port == port

    def test_hostname_support(self):
        """Test that hostname is supported."""
        conn = TCPMeshCoreConnection(host="meshcore.local")
        assert conn.host == "meshcore.local"

    def test_ipv4_addresses(self):
        """Test various IPv4 addresses."""
        addresses = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "127.0.0.1"
        ]

        for addr in addresses:
            conn = TCPMeshCoreConnection(host=addr)
            assert conn.host == addr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
