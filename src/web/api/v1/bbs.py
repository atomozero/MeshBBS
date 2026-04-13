"""
BBS control API endpoints.

Provides endpoints to monitor and control the BBS radio service
from the web administration interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status

from web.dependencies import get_current_admin, get_current_superadmin
from web.auth.models import AdminUser
from meshbbs_radio.state import get_state_manager


router = APIRouter(prefix="/bbs", tags=["BBS Control"])


@router.get("/status")
async def get_bbs_status(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Get BBS service status.

    Returns the current state of the BBS radio service including
    connection info, uptime, and process status.
    """
    state_manager = get_state_manager()
    state = state_manager.state

    # Check if BBS instance is running
    try:
        from bbs.runtime import get_bbs_instance
        bbs = get_bbs_instance()
        bbs_running = bbs is not None and bbs._running
    except ImportError:
        bbs_running = None  # Launcher not used

    result = {
        "bbs_running": bbs_running,
        "radio": state_manager.to_dict(),
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Add uptime if connected
    if state.connected_at:
        uptime = (datetime.utcnow() - state.connected_at).total_seconds()
        result["radio_uptime_seconds"] = int(uptime)

    return result


@router.post("/restart")
async def restart_bbs(
    admin: AdminUser = Depends(get_current_superadmin),
):
    """
    Restart the BBS radio service.

    Stops the current BBS instance, disconnects from the radio,
    and starts a new connection. Requires superadmin privileges.
    """
    try:
        from bbs.runtime import get_bbs_instance
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Restart disponibile solo con il launcher unificato",
        )

    bbs = get_bbs_instance()
    if bbs is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servizio BBS non attivo",
        )

    async def _do_restart():
        """Perform restart in background."""
        import launcher
        from utils.config import get_config

        config = get_config()

        # Stop current instance
        await bbs.stop()
        launcher._bbs_instance = None

        # Brief pause to let radio reset
        await asyncio.sleep(2)

        # Start new instance
        from bbs.core import BBSCore
        new_bbs = BBSCore(config)
        launcher._bbs_instance = new_bbs

        await new_bbs.start()
        asyncio.create_task(new_bbs.run())

    # Launch restart as background task
    asyncio.create_task(_do_restart())

    return {
        "message": "Riavvio BBS in corso",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/advert")
async def send_advert(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Send a manual advertisement on the mesh network.

    Forces the BBS to announce its presence immediately.
    """
    try:
        from bbs.runtime import get_bbs_instance
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Disponibile solo con il launcher unificato",
        )

    bbs = get_bbs_instance()
    if bbs is None or not bbs._running:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servizio BBS non attivo",
        )

    success = await bbs.connection.send_advert(flood=True)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invio advertisement fallito",
        )

    try:
        from bbs.models.base import get_session
        from bbs.models.activity_log import EventType, log_activity

        with get_session() as session:
            log_activity(
                session,
                EventType.ADVERT_SENT,
                details=f"Manuale da web ({admin.username})",
            )
    except Exception:
        pass

    return {
        "message": "Advertisement inviato",
        "timestamp": datetime.utcnow().isoformat(),
    }
