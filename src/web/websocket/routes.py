"""
WebSocket routes for real-time updates.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from fastapi.websockets import WebSocketState

from web.auth.jwt import decode_access_token
from web.auth.models import AdminUserRepository
from web.dependencies import get_db_session
from web.websocket.manager import get_connection_manager, EventType


logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time updates.

    Authentication via query parameter: ?token=<access_token>

    Message format (incoming):
    {
        "action": "subscribe" | "unsubscribe" | "ping",
        "topics": ["users", "messages", "system"]  // for subscribe/unsubscribe
    }

    Message format (outgoing):
    {
        "type": "event_type",
        "data": {...},
        "timestamp": "ISO8601"
    }
    """
    manager = get_connection_manager()

    # Authenticate
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token mancante")
        return

    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token non valido")
        return

    admin_id = payload.get("sub")
    if not admin_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token non valido")
        return

    # Verify admin exists
    db = next(get_db_session())
    try:
        repo = AdminUserRepository(db)
        admin = repo.get_by_id(int(admin_id))
        if not admin or not admin.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Admin non autorizzato")
            return

        username = admin.username
    finally:
        db.close()

    # Connect
    try:
        client = await manager.connect(websocket, int(admin_id), username)

        # Handle messages
        while True:
            try:
                data = await websocket.receive_json()
                await handle_client_message(manager, int(admin_id), data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.warning(f"WebSocket error for admin {admin_id}: {e}")
                await manager.send_personal(int(admin_id), {
                    "type": EventType.ERROR,
                    "data": {"message": str(e)},
                })

    finally:
        await manager.disconnect(int(admin_id))


async def handle_client_message(manager, admin_id: int, data: dict):
    """
    Handle incoming WebSocket messages from clients.

    Args:
        manager: ConnectionManager instance
        admin_id: Admin user ID
        data: Message data
    """
    action = data.get("action")

    if action == "subscribe":
        topics = data.get("topics", [])
        if isinstance(topics, list):
            await manager.subscribe(admin_id, topics)
            await manager.send_personal(admin_id, {
                "type": "subscribed",
                "data": {"topics": topics},
            })

    elif action == "unsubscribe":
        topics = data.get("topics", [])
        if isinstance(topics, list):
            await manager.unsubscribe(admin_id, topics)
            await manager.send_personal(admin_id, {
                "type": "unsubscribed",
                "data": {"topics": topics},
            })

    elif action == "ping":
        await manager.send_personal(admin_id, {
            "type": "pong",
            "data": {},
        })

    elif action == "get_status":
        # Send current connection status
        await manager.send_personal(admin_id, {
            "type": "status",
            "data": {
                "connected_admins": manager.connected_admins,
                "connection_count": manager.connection_count,
            },
        })

    else:
        await manager.send_personal(admin_id, {
            "type": EventType.ERROR,
            "data": {"message": f"Azione sconosciuta: {action}"},
        })
