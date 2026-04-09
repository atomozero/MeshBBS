"""
Radio connection status API endpoints.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from web.dependencies import get_current_admin
from web.auth.models import AdminUser
from meshcore.state import get_state_manager, ConnectionStatus


router = APIRouter(prefix="/radio", tags=["Radio"])


class RadioInfoResponse(BaseModel):
    """Radio hardware information."""

    public_key: str
    name: str
    port: str
    baud_rate: int
    is_mock: bool
    battery_level: Optional[int] = None
    battery_charging: bool = False


class RadioStatusResponse(BaseModel):
    """Radio connection status response."""

    status: str
    is_connected: bool
    radio: Optional[RadioInfoResponse] = None
    connected_at: Optional[str] = None
    last_activity: Optional[str] = None
    error: Optional[str] = None
    message_count: int = 0
    reconnect_attempts: int = 0


@router.get("/status", response_model=RadioStatusResponse)
async def get_radio_status(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Get current radio connection status.

    Returns detailed information about the MeshCore radio connection
    including status, hardware info, and activity metrics.
    """
    state_manager = get_state_manager()
    state = state_manager.state

    radio_info = None
    if state_manager.is_connected:
        radio_info = RadioInfoResponse(
            public_key=state.radio_info.public_key,
            name=state.radio_info.name,
            port=state.radio_info.port,
            baud_rate=state.radio_info.baud_rate,
            is_mock=state.radio_info.is_mock,
            battery_level=state.radio_info.battery_level,
            battery_charging=state.radio_info.battery_charging,
        )

    return RadioStatusResponse(
        status=state.status.value,
        is_connected=state_manager.is_connected,
        radio=radio_info,
        connected_at=state.connected_at.isoformat() if state.connected_at else None,
        last_activity=state.last_activity.isoformat() if state.last_activity else None,
        error=state.error_message,
        message_count=state.message_count,
        reconnect_attempts=state.reconnect_attempts,
    )


@router.get("/health")
async def radio_health_check():
    """
    Quick health check for radio connection (no auth required).

    Returns simple connected/disconnected status.
    """
    state_manager = get_state_manager()

    return {
        "connected": state_manager.is_connected,
        "status": state_manager.status.value,
        "timestamp": datetime.utcnow().isoformat(),
    }
