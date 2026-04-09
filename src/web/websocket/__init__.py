"""
WebSocket module for real-time updates.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from web.websocket.manager import ConnectionManager, get_connection_manager
from web.websocket.routes import router as websocket_router

__all__ = [
    "ConnectionManager",
    "get_connection_manager",
    "websocket_router",
]
