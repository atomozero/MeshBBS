"""
Tests for MeshCore connection state management.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import pytest
from pathlib import Path
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshbbs_radio.state import (
    MeshCoreStateManager,
    ConnectionStatus,
    ConnectionState,
    RadioInfo,
    get_state_manager,
    reset_state_manager,
)


class TestConnectionStatus:
    """Test ConnectionStatus enum."""

    def test_status_values(self):
        """Test status enum has expected values."""
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.RECONNECTING.value == "reconnecting"
        assert ConnectionStatus.ERROR.value == "error"


class TestRadioInfo:
    """Test RadioInfo dataclass."""

    def test_default_values(self):
        """Test RadioInfo has sensible defaults."""
        info = RadioInfo()

        assert info.public_key == ""
        assert info.name == ""
        assert info.port == ""
        assert info.baud_rate == 115200
        assert info.is_mock is False
        assert info.battery_level is None
        assert info.battery_charging is False

    def test_custom_values(self):
        """Test RadioInfo with custom values."""
        info = RadioInfo(
            public_key="abc123",
            name="TestRadio",
            port="/dev/ttyUSB0",
            baud_rate=9600,
            is_mock=True,
            battery_level=75,
            battery_charging=True,
        )

        assert info.public_key == "abc123"
        assert info.name == "TestRadio"
        assert info.port == "/dev/ttyUSB0"
        assert info.baud_rate == 9600
        assert info.is_mock is True
        assert info.battery_level == 75
        assert info.battery_charging is True


class TestConnectionState:
    """Test ConnectionState dataclass."""

    def test_default_state(self):
        """Test ConnectionState has sensible defaults."""
        state = ConnectionState()

        assert state.status == ConnectionStatus.DISCONNECTED
        assert isinstance(state.radio_info, RadioInfo)
        assert state.connected_at is None
        assert state.last_activity is None
        assert state.error_message is None
        assert state.message_count == 0
        assert state.reconnect_attempts == 0


class TestMeshCoreStateManager:
    """Test MeshCoreStateManager functionality."""

    @pytest.fixture
    def manager(self):
        """Create a fresh state manager for each test."""
        reset_state_manager()
        return MeshCoreStateManager()

    def test_initial_state(self, manager):
        """Test initial state is disconnected."""
        assert manager.is_connected is False
        assert manager.status == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_set_connecting(self, manager):
        """Test setting state to connecting."""
        await manager.set_connecting("/dev/ttyUSB0", 115200)

        assert manager.status == ConnectionStatus.CONNECTING
        assert manager.state.radio_info.port == "/dev/ttyUSB0"
        assert manager.state.radio_info.baud_rate == 115200
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_set_connected(self, manager):
        """Test setting state to connected."""
        await manager.set_connected(
            public_key="abc123",
            name="TestRadio",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            is_mock=False,
        )

        assert manager.is_connected is True
        assert manager.status == ConnectionStatus.CONNECTED
        assert manager.state.radio_info.public_key == "abc123"
        assert manager.state.radio_info.name == "TestRadio"
        assert manager.state.connected_at is not None
        assert manager.state.last_activity is not None

    @pytest.mark.asyncio
    async def test_set_disconnected(self, manager):
        """Test setting state to disconnected."""
        # First connect
        await manager.set_connected("key", "name", "/port", 115200, False)
        assert manager.is_connected is True

        # Then disconnect
        await manager.set_disconnected()

        assert manager.is_connected is False
        assert manager.status == ConnectionStatus.DISCONNECTED
        assert manager.state.connected_at is None

    @pytest.mark.asyncio
    async def test_set_disconnected_with_error(self, manager):
        """Test setting state to disconnected with error."""
        await manager.set_disconnected(error="Connection lost")

        assert manager.is_connected is False
        assert manager.state.error_message == "Connection lost"

    @pytest.mark.asyncio
    async def test_set_error(self, manager):
        """Test setting state to error."""
        await manager.set_error("Hardware failure")

        assert manager.status == ConnectionStatus.ERROR
        assert manager.state.error_message == "Hardware failure"

    @pytest.mark.asyncio
    async def test_set_reconnecting(self, manager):
        """Test setting state to reconnecting."""
        await manager.set_reconnecting(attempt=3)

        assert manager.status == ConnectionStatus.RECONNECTING
        assert manager.state.reconnect_attempts == 3

    @pytest.mark.asyncio
    async def test_update_activity(self, manager):
        """Test updating activity timestamp."""
        await manager.set_connected("key", "name", "/port", 115200, False)
        initial_count = manager.state.message_count

        await manager.update_activity()

        assert manager.state.message_count == initial_count + 1
        assert manager.state.last_activity is not None

    @pytest.mark.asyncio
    async def test_update_battery(self, manager):
        """Test updating battery info."""
        await manager.set_connected("key", "name", "/port", 115200, False)

        await manager.update_battery(level=85, charging=True)

        assert manager.state.radio_info.battery_level == 85
        assert manager.state.radio_info.battery_charging is True

    @pytest.mark.asyncio
    async def test_to_dict_disconnected(self, manager):
        """Test converting disconnected state to dict."""
        data = manager.to_dict()

        assert data["status"] == "disconnected"
        assert data["is_connected"] is False
        assert data["radio"] is None
        assert data["connected_at"] is None

    @pytest.mark.asyncio
    async def test_to_dict_connected(self, manager):
        """Test converting connected state to dict."""
        await manager.set_connected(
            public_key="abc123",
            name="TestRadio",
            port="/dev/ttyUSB0",
            baud_rate=115200,
            is_mock=True,
        )

        data = manager.to_dict()

        assert data["status"] == "connected"
        assert data["is_connected"] is True
        assert data["radio"]["public_key"] == "abc123"
        assert data["radio"]["name"] == "TestRadio"
        assert data["radio"]["is_mock"] is True
        assert data["connected_at"] is not None

    @pytest.mark.asyncio
    async def test_listeners(self, manager):
        """Test state change listeners."""
        events = []

        def listener(state):
            events.append(state.status)

        manager.add_listener(listener)

        await manager.set_connecting("/port", 115200)
        await manager.set_connected("key", "name", "/port", 115200, False)
        await manager.set_disconnected()

        assert len(events) == 3
        assert events[0] == ConnectionStatus.CONNECTING
        assert events[1] == ConnectionStatus.CONNECTED
        assert events[2] == ConnectionStatus.DISCONNECTED

    @pytest.mark.asyncio
    async def test_async_listener(self, manager):
        """Test async state change listener."""
        events = []

        async def async_listener(state):
            events.append(state.status)

        manager.add_listener(async_listener)

        await manager.set_connected("key", "name", "/port", 115200, False)

        assert len(events) == 1
        assert events[0] == ConnectionStatus.CONNECTED

    @pytest.mark.asyncio
    async def test_remove_listener(self, manager):
        """Test removing a listener."""
        events = []

        def listener(state):
            events.append(state.status)

        manager.add_listener(listener)
        await manager.set_connecting("/port", 115200)

        manager.remove_listener(listener)
        await manager.set_connected("key", "name", "/port", 115200, False)

        # Only first event should be captured
        assert len(events) == 1


class TestGlobalStateManager:
    """Test global state manager singleton."""

    def setup_method(self):
        """Reset global state before each test."""
        reset_state_manager()

    def test_get_state_manager_singleton(self):
        """Test get_state_manager returns singleton."""
        manager1 = get_state_manager()
        manager2 = get_state_manager()

        assert manager1 is manager2

    def test_reset_state_manager(self):
        """Test reset creates new instance."""
        manager1 = get_state_manager()
        reset_state_manager()
        manager2 = get_state_manager()

        assert manager1 is not manager2

    @pytest.mark.asyncio
    async def test_global_state_persistence(self):
        """Test that global state persists across calls."""
        manager1 = get_state_manager()
        await manager1.set_connected("key", "name", "/port", 115200, False)

        manager2 = get_state_manager()

        assert manager2.is_connected is True
        assert manager2.state.radio_info.public_key == "key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
