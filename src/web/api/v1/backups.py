"""
Backup management endpoints.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import os

from web.dependencies import get_current_superadmin
from web.auth.models import AdminUser

# Try to import backup module
try:
    from utils.backup import BackupManager, BackupConfig
    BACKUP_AVAILABLE = True
except ImportError:
    BACKUP_AVAILABLE = False
    BackupManager = None
    BackupConfig = None

router = APIRouter(prefix="/backups", tags=["backups"])


# Schemas
class BackupInfo(BaseModel):
    name: str
    path: str
    size: int
    size_human: str
    created_at: str
    compressed: bool


class BackupListResponse(BaseModel):
    items: List[BackupInfo]
    total: int


class BackupCreateRequest(BaseModel):
    label: Optional[str] = None


class BackupCreateResponse(BaseModel):
    success: bool
    message: str
    backup: Optional[BackupInfo] = None


class BackupRestoreRequest(BaseModel):
    backup_name: str


class BackupRestoreResponse(BaseModel):
    success: bool
    message: str


class BackupDeleteResponse(BaseModel):
    success: bool
    message: str


def get_backup_manager() -> Optional['BackupManager']:
    """Get backup manager instance."""
    if not BACKUP_AVAILABLE:
        return None

    config = BackupConfig.from_env()
    database_path = os.getenv('DATABASE_PATH', '/var/lib/meshbbs/meshbbs.db')

    return BackupManager(
        database_path=database_path,
        backup_dir=config.backup_dir,
        max_backups=config.max_backups,
        compress=config.compress,
    )


@router.get("", response_model=BackupListResponse)
async def list_backups(
    current_user: AdminUser = Depends(get_current_superadmin)
):
    """
    List all available backups.

    Requires superadmin privileges.
    """
    manager = get_backup_manager()

    if not manager:
        raise HTTPException(
            status_code=501,
            detail="Backup functionality not available"
        )

    backups = manager.list_backups()

    return BackupListResponse(
        items=[BackupInfo(**b) for b in backups],
        total=len(backups)
    )


@router.post("", response_model=BackupCreateResponse)
async def create_backup(
    request: BackupCreateRequest = None,
    background_tasks: BackgroundTasks = None,
    current_user: AdminUser = Depends(get_current_superadmin)
):
    """
    Create a new backup.

    Requires superadmin privileges.
    """
    manager = get_backup_manager()

    if not manager:
        raise HTTPException(
            status_code=501,
            detail="Backup functionality not available"
        )

    label = request.label if request else None
    backup_path = manager.create_backup(label=label or "manual")

    if backup_path:
        backups = manager.list_backups()
        backup_info = next(
            (b for b in backups if b['path'] == str(backup_path)),
            None
        )

        return BackupCreateResponse(
            success=True,
            message="Backup created successfully",
            backup=BackupInfo(**backup_info) if backup_info else None
        )
    else:
        return BackupCreateResponse(
            success=False,
            message="Backup creation failed"
        )


@router.post("/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    request: BackupRestoreRequest,
    current_user: AdminUser = Depends(get_current_superadmin)
):
    """
    Restore database from a backup.

    WARNING: This will overwrite the current database!
    A safety backup is created before restoration.

    Requires superadmin privileges.
    """
    manager = get_backup_manager()

    if not manager:
        raise HTTPException(
            status_code=501,
            detail="Backup functionality not available"
        )

    # Find backup by name
    backups = manager.list_backups()
    backup = next(
        (b for b in backups if b['name'] == request.backup_name),
        None
    )

    if not backup:
        raise HTTPException(
            status_code=404,
            detail=f"Backup not found: {request.backup_name}"
        )

    success = manager.restore_backup(backup['path'])

    if success:
        return BackupRestoreResponse(
            success=True,
            message="Database restored successfully. Please restart the services."
        )
    else:
        return BackupRestoreResponse(
            success=False,
            message="Restore failed. Check logs for details."
        )


@router.delete("/{backup_name}", response_model=BackupDeleteResponse)
async def delete_backup(
    backup_name: str,
    current_user: AdminUser = Depends(get_current_superadmin)
):
    """
    Delete a specific backup.

    Requires superadmin privileges.
    """
    manager = get_backup_manager()

    if not manager:
        raise HTTPException(
            status_code=501,
            detail="Backup functionality not available"
        )

    # Validate backup exists
    backups = manager.list_backups()
    backup = next(
        (b for b in backups if b['name'] == backup_name),
        None
    )

    if not backup:
        raise HTTPException(
            status_code=404,
            detail=f"Backup not found: {backup_name}"
        )

    success = manager.delete_backup(backup_name)

    if success:
        return BackupDeleteResponse(
            success=True,
            message="Backup deleted successfully"
        )
    else:
        return BackupDeleteResponse(
            success=False,
            message="Failed to delete backup"
        )


@router.get("/config")
async def get_backup_config(
    current_user: AdminUser = Depends(get_current_superadmin)
):
    """
    Get current backup configuration.

    Requires superadmin privileges.
    """
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Backup functionality not available"
        )

    config = BackupConfig.from_env()

    return {
        "enabled": config.enabled,
        "interval_hours": config.interval_hours,
        "max_backups": config.max_backups,
        "compress": config.compress,
        "backup_dir": config.backup_dir,
    }
