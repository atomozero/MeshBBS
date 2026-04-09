"""
Activity logs API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from bbs.models.activity_log import ActivityLog, EventType
from bbs.models.user import User


router = APIRouter(prefix="/logs", tags=["Logs"])


class LogEntryResponse(BaseModel):
    """Activity log entry response."""

    id: int
    event_type: str
    user_key: Optional[str]
    user_nickname: Optional[str]
    details: Optional[str]
    timestamp: Optional[str]


class LogListResponse(BaseModel):
    """Activity log list response."""

    items: List[LogEntryResponse]
    total: int
    page: int
    per_page: int
    pages: int


class LogStatsResponse(BaseModel):
    """Log statistics response."""

    total_entries: int
    entries_today: int
    entries_week: int
    by_type: dict


@router.get("", response_model=LogListResponse)
async def list_logs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
    user_key: Optional[str] = Query(default=None, description="Filter by user"),
    search: Optional[str] = Query(default=None, max_length=100, description="Search in details"),
    start_date: Optional[str] = Query(default=None, description="Start date (ISO)"),
    end_date: Optional[str] = Query(default=None, description="End date (ISO)"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List activity logs with filtering and pagination.
    """
    query = db.query(ActivityLog)

    # Filter by event type
    if event_type:
        query = query.filter(ActivityLog.event_type == event_type)

    # Filter by user
    if user_key:
        # Find user by key or nickname
        user = db.query(User).filter(
            or_(
                User.public_key.startswith(user_key),
                User.nickname.ilike(user_key),
            )
        ).first()
        if user:
            query = query.filter(ActivityLog.user_key == user.public_key)
        else:
            query = query.filter(ActivityLog.user_key.startswith(user_key))

    # Search in details
    if search:
        query = query.filter(ActivityLog.details.ilike(f"%{search}%"))

    # Date filters
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.timestamp >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.timestamp <= end)
        except ValueError:
            pass

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    logs = (
        query.order_by(ActivityLog.timestamp.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Convert to response
    items = []
    for log in logs:
        nickname = None
        if log.user_key:
            user = db.query(User).filter(User.public_key == log.user_key).first()
            if user:
                nickname = user.nickname

        items.append(LogEntryResponse(
            id=log.id,
            event_type=log.event_type,
            user_key=log.user_key,
            user_nickname=nickname,
            details=log.details,
            timestamp=log.timestamp.isoformat() if log.timestamp else None,
        ))

    pages = (total + per_page - 1) // per_page

    return LogListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/types")
async def list_event_types(
    admin: AdminUser = Depends(get_current_admin),
):
    """
    List all available event types.
    """
    return {
        "types": [
            {"value": e.value, "name": e.name}
            for e in EventType
        ]
    }


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get log statistics.
    """
    from datetime import timedelta

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    total = db.query(ActivityLog).count()
    today = db.query(ActivityLog).filter(ActivityLog.timestamp >= today_start).count()
    week = db.query(ActivityLog).filter(ActivityLog.timestamp >= week_ago).count()

    # Count by type
    from sqlalchemy import func
    by_type_query = (
        db.query(ActivityLog.event_type, func.count(ActivityLog.id))
        .group_by(ActivityLog.event_type)
        .all()
    )
    by_type = {event_type: count for event_type, count in by_type_query}

    return LogStatsResponse(
        total_entries=total,
        entries_today=today,
        entries_week=week,
        by_type=by_type,
    )


@router.delete("")
async def clear_old_logs(
    days: int = Query(default=90, ge=1, le=365, description="Delete logs older than N days"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete logs older than specified days.

    Requires superadmin privileges.
    """
    if not admin.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Richiesti privilegi di superadmin",
        )

    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)
    deleted = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff).delete()
    db.commit()

    return {
        "message": f"Eliminati {deleted} log più vecchi di {days} giorni",
        "deleted_count": deleted,
    }


@router.get("/export")
async def export_logs(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=1000, ge=1, le=10000),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Export logs in JSON or CSV format.
    """
    query = db.query(ActivityLog)

    # Date filters
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.timestamp >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(ActivityLog.timestamp <= end)
        except ValueError:
            pass

    logs = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()

    if format == "csv":
        # Return CSV format
        from fastapi.responses import PlainTextResponse

        lines = ["id,event_type,user_key,details,timestamp"]
        for log in logs:
            details = (log.details or "").replace('"', '""')
            lines.append(
                f'{log.id},{log.event_type},{log.user_key or ""},"{details}",{log.timestamp.isoformat() if log.timestamp else ""}'
            )

        return PlainTextResponse(
            content="\n".join(lines),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=logs.csv"},
        )

    # Return JSON format
    return {
        "logs": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "user_key": log.user_key,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ],
        "count": len(logs),
    }
