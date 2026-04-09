"""
Tests for real-time WebSocket broadcasting from BBS core.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from web.websocket.manager import ConnectionManager, EventType


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    def test_initial_state(self):
        """Manager starts with no connections."""
        manager = ConnectionManager()
        assert manager.connection_count == 0
        assert manager.connected_admins == []

    @pytest.mark.asyncio
    async def test_broadcast_stats_update(self):
        """Verify broadcast_stats_update sends correct event type."""
        manager = ConnectionManager()

        # Mock a connected client
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        await manager.connect(mock_ws, admin_id=1, username="admin")

        stats = {"users": {"total": 10}, "messages": {"public": {"total": 50}}}
        await manager.broadcast_stats_update(stats)

        # Check that send_json was called (welcome + stats)
        calls = mock_ws.send_json.call_args_list
        stats_call = [c for c in calls if c[0][0].get("type") == EventType.STATS_UPDATE]
        assert len(stats_call) == 1
        assert stats_call[0][0][0]["data"] == stats

    @pytest.mark.asyncio
    async def test_broadcast_system_status(self):
        """Verify broadcast_system_status sends correct event type."""
        manager = ConnectionManager()

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        await manager.connect(mock_ws, admin_id=1, username="admin")
        await manager.subscribe(1, ["system"])

        status = {"status": "connected", "is_connected": True, "message_count": 42}
        await manager.broadcast_system_status(status)

        calls = mock_ws.send_json.call_args_list
        status_calls = [c for c in calls if c[0][0].get("type") == EventType.SYSTEM_STATUS]
        assert len(status_calls) == 1
        assert status_calls[0][0][0]["data"]["is_connected"] is True

    @pytest.mark.asyncio
    async def test_broadcast_message_event(self):
        """Verify broadcast_message_event sends correct event type."""
        manager = ConnectionManager()

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        # Subscribe to messages topic
        await manager.connect(mock_ws, admin_id=1, username="admin")
        await manager.subscribe(1, ["messages"])

        msg_data = {"sender_key": "A" * 64, "text": "Hello mesh"}
        await manager.broadcast_message_event(EventType.NEW_MESSAGE, msg_data)

        calls = mock_ws.send_json.call_args_list
        msg_calls = [c for c in calls if c[0][0].get("type") == EventType.NEW_MESSAGE]
        assert len(msg_calls) == 1
        assert msg_calls[0][0][0]["data"]["text"] == "Hello mesh"

    @pytest.mark.asyncio
    async def test_no_broadcast_to_empty_room(self):
        """Verify no errors when broadcasting with no clients."""
        manager = ConnectionManager()
        # Should not raise
        await manager.broadcast_stats_update({"test": True})
        await manager.broadcast_system_status({"status": "ok"})

    @pytest.mark.asyncio
    async def test_connection_count(self):
        """Verify connection_count tracks connected clients."""
        manager = ConnectionManager()

        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        assert manager.connection_count == 0

        await manager.connect(mock_ws, admin_id=1, username="admin1")
        assert manager.connection_count == 1

        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()
        mock_ws2.close = AsyncMock()

        await manager.connect(mock_ws2, admin_id=2, username="admin2")
        assert manager.connection_count == 2


class TestCoreWSIntegration:
    """Tests for BBS core WebSocket notification methods."""

    @pytest.mark.asyncio
    async def test_ws_notify_message(self, config, mock_connection):
        """Verify _ws_notify_message broadcasts to WebSocket."""
        from bbs.core import BBSCore
        from meshcore.messages import Message

        bbs = BBSCore(config, connection=mock_connection)

        mock_manager = MagicMock()
        mock_manager.connection_count = 1
        mock_manager.broadcast_message_event = AsyncMock()

        msg = Message(
            sender_key="A" * 64,
            text="!help",
            hops=2,
            rssi=-85,
        )

        with patch("web.websocket.manager.get_connection_manager", return_value=mock_manager):
            await bbs._ws_notify_message(msg)

        mock_manager.broadcast_message_event.assert_called_once()
        call_args = mock_manager.broadcast_message_event.call_args[0]
        # args: (event_type, message_data)
        assert call_args[1]["hops"] == 2

    @pytest.mark.asyncio
    async def test_ws_notify_skipped_when_no_clients(self, config, mock_connection):
        """Verify notification is skipped when no WebSocket clients connected."""
        from bbs.core import BBSCore
        from meshcore.messages import Message

        bbs = BBSCore(config, connection=mock_connection)

        mock_manager = MagicMock()
        mock_manager.connection_count = 0
        mock_manager.broadcast_message_event = AsyncMock()

        msg = Message(sender_key="A" * 64, text="!help")

        with patch("web.websocket.manager.get_connection_manager", return_value=mock_manager):
            await bbs._ws_notify_message(msg)

        mock_manager.broadcast_message_event.assert_not_called()


class TestEventTypes:
    """Tests for WebSocket event type definitions."""

    def test_event_types_exist(self):
        """Verify all expected event types are defined."""
        assert EventType.STATS_UPDATE == "stats_update"
        assert EventType.SYSTEM_STATUS == "system_status"
        assert EventType.NEW_MESSAGE == "new_message"
        assert EventType.ACTIVITY == "activity"
        assert EventType.CONNECTED == "connected"
        assert EventType.DISCONNECTED == "disconnected"
