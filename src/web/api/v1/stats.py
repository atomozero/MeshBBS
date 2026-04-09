"""
Statistics API endpoints for MeshCore BBS.

Provides a unified statistics endpoint for external consumption
(Grafana, Home Assistant, custom dashboards, etc.).

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from bbs.services.stats_collector import StatsCollector


router = APIRouter(prefix="/stats", tags=["Statistics"])


@router.get("")
async def get_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get unified BBS usage statistics.

    Returns a single JSON payload with all metrics:
    users, messages, radio, delivery, and system info.

    This is the same payload published via MQTT on meshbbs/stats.
    """
    collector = StatsCollector(db)
    return collector.collect()


@router.get("/health")
async def stats_health():
    """
    Lightweight health check (no auth required).

    Returns basic radio status without database queries.
    """
    from meshcore.state import get_state_manager

    state_manager = get_state_manager()
    state = state_manager.state

    return {
        "status": "ok" if state_manager.is_connected else "degraded",
        "radio_connected": state_manager.is_connected,
        "messages_processed": state.message_count,
    }
