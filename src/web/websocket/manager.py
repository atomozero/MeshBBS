"""
WebSocket connection manager for real-time updates.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Any

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """WebSocket event types."""

    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

    # User events
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_BANNED = "user_banned"
    USER_UNBANNED = "user_unbanned"

    # Message events
    NEW_MESSAGE = "new_message"
    MESSAGE_DELETED = "message_deleted"

    # System events
    SYSTEM_STATUS = "system_status"
    STATS_UPDATE = "stats_update"
    ACTIVITY = "activity"

    # Area events
    AREA_CREATED = "area_created"
    AREA_DELETED = "area_deleted"


@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client."""

    websocket: WebSocket
    admin_id: int
    username: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    subscriptions: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(id(self.websocket))


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.

    Features:
    - Connection tracking per admin user
    - Topic-based subscriptions
    - Broadcast to all or specific users
    - Automatic cleanup on disconnect
    """

    def __init__(self):
        self._connections: Dict[int, WebSocketClient] = {}
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self._connections)

    @property
    def connected_admins(self) -> List[str]:
        """Get list of connected admin usernames."""
        return [client.username for client in self._connections.values()]

    async def connect(
        self,
        websocket: WebSocket,
        admin_id: int,
        username: str,
    ) -> WebSocketClient:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            admin_id: Admin user ID
            username: Admin username

        Returns:
            WebSocketClient instance
        """
        await websocket.accept()

        client = WebSocketClient(
            websocket=websocket,
            admin_id=admin_id,
            username=username,
        )

        async with self._lock:
            # Close existing connection for same admin if any
            if admin_id in self._connections:
                old_client = self._connections[admin_id]
                try:
                    await old_client.websocket.close(code=1000, reason="New connection")
                except Exception:
                    pass

            self._connections[admin_id] = client

        logger.info(f"WebSocket connected: {username} (admin_id={admin_id})")

        # Send welcome message
        await self.send_personal(admin_id, {
            "type": EventType.CONNECTED,
            "data": {
                "message": f"Benvenuto, {username}!",
                "connected_admins": self.connected_admins,
                "timestamp": datetime.utcnow().isoformat(),
            },
        })

        # Notify others
        await self.broadcast({
            "type": EventType.ACTIVITY,
            "data": {
                "message": f"Admin {username} connesso",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }, exclude=[admin_id])

        return client

    async def disconnect(self, admin_id: int):
        """
        Disconnect and unregister a WebSocket connection.

        Args:
            admin_id: Admin user ID
        """
        async with self._lock:
            if admin_id in self._connections:
                client = self._connections.pop(admin_id)
                username = client.username

                try:
                    await client.websocket.close()
                except Exception:
                    pass

                logger.info(f"WebSocket disconnected: {username} (admin_id={admin_id})")

                # Notify others
                await self._broadcast_internal({
                    "type": EventType.DISCONNECTED,
                    "data": {
                        "username": username,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                })

    async def subscribe(self, admin_id: int, topics: List[str]):
        """
        Subscribe a client to specific topics.

        Args:
            admin_id: Admin user ID
            topics: List of topic names
        """
        if admin_id in self._connections:
            self._connections[admin_id].subscriptions.update(topics)
            logger.debug(f"Admin {admin_id} subscribed to: {topics}")

    async def unsubscribe(self, admin_id: int, topics: List[str]):
        """
        Unsubscribe a client from specific topics.

        Args:
            admin_id: Admin user ID
            topics: List of topic names
        """
        if admin_id in self._connections:
            self._connections[admin_id].subscriptions.difference_update(topics)
            logger.debug(f"Admin {admin_id} unsubscribed from: {topics}")

    async def send_personal(self, admin_id: int, message: dict):
        """
        Send a message to a specific admin.

        Args:
            admin_id: Admin user ID
            message: Message dictionary
        """
        if admin_id in self._connections:
            client = self._connections[admin_id]
            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to admin {admin_id}: {e}")
                await self.disconnect(admin_id)

    async def broadcast(
        self,
        message: dict,
        exclude: Optional[List[int]] = None,
        topic: Optional[str] = None,
    ):
        """
        Broadcast a message to all connected clients.

        Args:
            message: Message dictionary
            exclude: List of admin IDs to exclude
            topic: If specified, only send to clients subscribed to this topic
        """
        async with self._lock:
            await self._broadcast_internal(message, exclude, topic)

    async def _broadcast_internal(
        self,
        message: dict,
        exclude: Optional[List[int]] = None,
        topic: Optional[str] = None,
    ):
        """Internal broadcast without lock (assumes lock is held)."""
        exclude = exclude or []
        disconnected = []

        for admin_id, client in self._connections.items():
            if admin_id in exclude:
                continue

            # Check topic subscription if specified
            if topic and topic not in client.subscriptions:
                continue

            try:
                await client.websocket.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to broadcast to admin {admin_id}: {e}")
                disconnected.append(admin_id)

        # Clean up disconnected clients
        for admin_id in disconnected:
            if admin_id in self._connections:
                del self._connections[admin_id]

    async def broadcast_stats_update(self, stats: dict):
        """
        Broadcast statistics update to all clients.

        Args:
            stats: Statistics dictionary
        """
        await self.broadcast({
            "type": EventType.STATS_UPDATE,
            "data": stats,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def broadcast_activity(self, activity: dict):
        """
        Broadcast activity event to all clients.

        Args:
            activity: Activity dictionary
        """
        await self.broadcast({
            "type": EventType.ACTIVITY,
            "data": activity,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def broadcast_user_event(self, event_type: EventType, user_data: dict):
        """
        Broadcast user-related event.

        Args:
            event_type: Type of user event
            user_data: User data dictionary
        """
        await self.broadcast({
            "type": event_type,
            "data": user_data,
            "timestamp": datetime.utcnow().isoformat(),
        }, topic="users")

    async def broadcast_message_event(self, event_type: EventType, message_data: dict):
        """
        Broadcast message-related event.

        Args:
            event_type: Type of message event
            message_data: Message data dictionary
        """
        await self.broadcast({
            "type": event_type,
            "data": message_data,
            "timestamp": datetime.utcnow().isoformat(),
        }, topic="messages")

    async def broadcast_system_status(self, status: dict):
        """
        Broadcast system status update.

        Args:
            status: System status dictionary
        """
        await self.broadcast({
            "type": EventType.SYSTEM_STATUS,
            "data": status,
            "timestamp": datetime.utcnow().isoformat(),
        }, topic="system")


# Singleton instance
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the singleton ConnectionManager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
