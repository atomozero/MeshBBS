"""
Settings API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import sys
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from web.dependencies import get_db, get_current_admin, get_current_superadmin
from web.auth.models import AdminUser
from web.schemas.stats import RetentionStats, RateLimitStats
from utils.config import get_config


router = APIRouter(prefix="/settings", tags=["Settings"])


class BBSSettingsResponse(BaseModel):
    """BBS settings response."""

    # General
    bbs_name: str
    default_area: str
    max_message_length: int

    # Location
    latitude: Optional[float]
    longitude: Optional[float]

    # Privacy
    pm_retention_days: int
    log_retention_days: int
    allow_ephemeral_pm: bool

    # Connection
    serial_port: str
    baud_rate: int

    # Paths
    database_path: str
    log_path: str


class BBSSettingsUpdateRequest(BaseModel):
    """BBS settings update request."""

    bbs_name: Optional[str] = Field(None, min_length=1, max_length=50)
    default_area: Optional[str] = Field(None, min_length=2, max_length=32)
    max_message_length: Optional[int] = Field(None, ge=50, le=1000)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    pm_retention_days: Optional[int] = Field(None, ge=0, le=365)
    log_retention_days: Optional[int] = Field(None, ge=0, le=365)
    allow_ephemeral_pm: Optional[bool] = None


class SystemInfoResponse(BaseModel):
    """System information response."""

    # Version info
    bbs_version: str
    web_version: str
    python_version: str

    # System
    platform: str
    hostname: str
    uptime_seconds: int

    # Database
    db_path: str
    db_size_bytes: int
    db_tables: dict

    # Memory (if available)
    memory_available: Optional[int]
    memory_total: Optional[int]


class MaintenanceRequest(BaseModel):
    """Maintenance operation request."""

    operation: str = Field(..., pattern="^(cleanup|vacuum|backup)$")
    dry_run: bool = False


class MaintenanceResponse(BaseModel):
    """Maintenance operation response."""

    operation: str
    success: bool
    message: str
    details: Optional[dict]


@router.get("", response_model=BBSSettingsResponse)
async def get_settings(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Get current BBS settings.
    """
    config = get_config()

    return BBSSettingsResponse(
        bbs_name=config.bbs_name,
        default_area=config.default_area,
        max_message_length=config.max_message_length,
        latitude=config.latitude,
        longitude=config.longitude,
        pm_retention_days=config.pm_retention_days,
        log_retention_days=config.activity_log_retention_days,
        allow_ephemeral_pm=config.allow_ephemeral_pm,
        serial_port=config.serial_port,
        baud_rate=config.baud_rate,
        database_path=config.database_path,
        log_path=config.log_path,
    )


@router.patch("", response_model=BBSSettingsResponse)
async def update_settings(
    request: BBSSettingsUpdateRequest,
    admin: AdminUser = Depends(get_current_superadmin),
):
    """
    Update BBS settings.

    Requires superadmin privileges.
    Note: Some settings may require restart to take effect.

    Updatable fields:
    - bbs_name: BBS display name
    - default_area: Default message area
    - max_message_length: Maximum message length
    - pm_retention_days: Days to keep private messages (0 = forever)
    - log_retention_days: Days to keep activity logs (0 = forever)
    - allow_ephemeral_pm: Allow ephemeral (non-saved) private messages
    """
    config = get_config()

    # Build updates dict from request (only non-None values)
    updates = {}
    if request.bbs_name is not None:
        updates["bbs_name"] = request.bbs_name
    if request.default_area is not None:
        updates["default_area"] = request.default_area
    if request.max_message_length is not None:
        updates["max_message_length"] = request.max_message_length
    if request.pm_retention_days is not None:
        updates["pm_retention_days"] = request.pm_retention_days
    if request.log_retention_days is not None:
        updates["activity_log_retention_days"] = request.log_retention_days
    if request.latitude is not None:
        updates["latitude"] = request.latitude
    if request.longitude is not None:
        updates["longitude"] = request.longitude
    if request.allow_ephemeral_pm is not None:
        updates["allow_ephemeral_pm"] = request.allow_ephemeral_pm

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nessun campo da aggiornare specificato",
        )

    # Apply updates
    try:
        changed = config.update(updates)
        if not changed:
            # No actual changes made
            pass
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante l'aggiornamento delle impostazioni: {str(e)}",
        )

    # Return updated config
    return BBSSettingsResponse(
        bbs_name=config.bbs_name,
        default_area=config.default_area,
        max_message_length=config.max_message_length,
        latitude=config.latitude,
        longitude=config.longitude,
        pm_retention_days=config.pm_retention_days,
        log_retention_days=config.activity_log_retention_days,
        allow_ephemeral_pm=config.allow_ephemeral_pm,
        serial_port=config.serial_port,
        baud_rate=config.baud_rate,
        database_path=config.database_path,
        log_path=config.log_path,
    )


@router.get("/retention", response_model=RetentionStats)
async def get_retention_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get retention policy statistics.
    """
    from bbs.privacy import RetentionManager

    config = get_config()
    manager = RetentionManager(db)

    stats = manager.get_retention_stats(
        pm_retention_days=config.pm_retention_days,
        log_retention_days=config.activity_log_retention_days,
    )

    # Get scheduler info if available
    last_cleanup = None
    next_cleanup = None

    return RetentionStats(
        pm_retention_days=config.pm_retention_days,
        log_retention_days=config.activity_log_retention_days,
        expired_pms=stats.get("expired_pms", 0),
        expired_logs=stats.get("expired_logs", 0),
        last_cleanup=last_cleanup,
        next_cleanup=next_cleanup,
    )


@router.get("/rate-limit", response_model=RateLimitStats)
async def get_rate_limit_stats(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    Get rate limiter statistics.
    """
    # Default values - in production would get from actual rate limiter
    return RateLimitStats(
        enabled=True,
        min_interval=1.0,
        max_per_minute=30,
        block_duration=60,
        currently_blocked=0,
        total_blocks_today=0,
    )


@router.get("/system", response_model=SystemInfoResponse)
async def get_system_info(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get system information.
    """
    import platform
    import socket
    import time

    from web import __version__ as web_version

    config = get_config()

    # Database info
    db_size = 0
    if os.path.exists(config.database_path):
        db_size = os.path.getsize(config.database_path)

    # Count tables
    from bbs.models.user import User
    from bbs.models.message import Message
    from bbs.models.area import Area
    from bbs.models.private_message import PrivateMessage
    from bbs.models.activity_log import ActivityLog
    from web.auth.models import AdminUser as AdminUserModel

    db_tables = {
        "users": db.query(User).count(),
        "messages": db.query(Message).count(),
        "areas": db.query(Area).count(),
        "private_messages": db.query(PrivateMessage).count(),
        "activity_logs": db.query(ActivityLog).count(),
        "admin_users": db.query(AdminUserModel).count(),
    }

    # Memory info (Linux only)
    memory_available = None
    memory_total = None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    memory_total = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    memory_available = int(line.split()[1]) * 1024
    except Exception:
        pass

    # Uptime
    uptime = int(time.time() - time.monotonic())

    return SystemInfoResponse(
        bbs_version="1.3.0",
        web_version=web_version,
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        hostname=socket.gethostname(),
        uptime_seconds=uptime,
        db_path=config.database_path,
        db_size_bytes=db_size,
        db_tables=db_tables,
        memory_available=memory_available,
        memory_total=memory_total,
    )


@router.post("/maintenance", response_model=MaintenanceResponse)
async def run_maintenance(
    request: MaintenanceRequest,
    admin: AdminUser = Depends(get_current_superadmin),
    db: Session = Depends(get_db),
):
    """
    Run maintenance operations.

    Operations:
    - cleanup: Run retention cleanup
    - vacuum: Optimize database
    - backup: Create database backup

    Requires superadmin privileges.
    """
    if request.operation == "cleanup":
        from bbs.privacy import RetentionManager

        config = get_config()
        manager = RetentionManager(db)

        if request.dry_run:
            stats = manager.get_retention_stats(
                pm_retention_days=config.pm_retention_days,
                log_retention_days=config.activity_log_retention_days,
            )
            return MaintenanceResponse(
                operation="cleanup",
                success=True,
                message="Dry run completato",
                details={
                    "pms_to_delete": stats.get("expired_pms", 0),
                    "logs_to_delete": stats.get("expired_logs", 0),
                },
            )

        pms_deleted, logs_deleted = manager.run_cleanup(
            pm_retention_days=config.pm_retention_days,
            log_retention_days=config.activity_log_retention_days,
        )
        db.commit()

        return MaintenanceResponse(
            operation="cleanup",
            success=True,
            message=f"Cleanup completato: {pms_deleted} PM, {logs_deleted} log eliminati",
            details={"pms_deleted": pms_deleted, "logs_deleted": logs_deleted},
        )

    elif request.operation == "vacuum":
        if request.dry_run:
            return MaintenanceResponse(
                operation="vacuum",
                success=True,
                message="VACUUM richiede accesso esclusivo al database",
                details=None,
            )

        # Run VACUUM
        db.execute("VACUUM")
        db.commit()

        return MaintenanceResponse(
            operation="vacuum",
            success=True,
            message="Database ottimizzato",
            details=None,
        )

    elif request.operation == "backup":
        import shutil
        from datetime import datetime

        config = get_config()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{config.database_path}.backup_{timestamp}"

        if request.dry_run:
            return MaintenanceResponse(
                operation="backup",
                success=True,
                message=f"Backup verrebbe creato in: {backup_path}",
                details={"backup_path": backup_path},
            )

        # Create backup
        shutil.copy2(config.database_path, backup_path)

        return MaintenanceResponse(
            operation="backup",
            success=True,
            message=f"Backup creato: {backup_path}",
            details={"backup_path": backup_path},
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Operazione non valida",
    )


@router.get("/health")
async def health_check():
    """
    Health check endpoint (no auth required).
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    }
