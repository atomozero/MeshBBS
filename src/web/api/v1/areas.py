"""
Areas API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from web.schemas.area import (
    AreaResponse,
    AreaListResponse,
    AreaCreateRequest,
    AreaUpdateRequest,
    AreaStatsResponse,
)
from web.schemas.common import SuccessResponse
from bbs.models.area import Area
from bbs.models.message import Message
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType
from bbs.repositories.area_repository import AreaRepository


router = APIRouter(prefix="/areas", tags=["Areas"])


# Protected area names that cannot be deleted
PROTECTED_AREAS = {"generale", "general"}


def area_to_response(area: Area) -> AreaResponse:
    """Convert Area model to response schema."""
    return AreaResponse(
        id=area.id,
        name=area.name,
        description=area.description,
        is_public=area.is_public,
        is_readonly=area.is_readonly,
        message_count=area.message_count,
        created_at=area.created_at.isoformat() if area.created_at else None,
        last_post_at=area.last_post_at.isoformat() if area.last_post_at else None,
    )


@router.get("", response_model=AreaListResponse)
async def list_areas(
    include_hidden: bool = Query(default=True, description="Include non-public areas"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List all areas.
    """
    query = db.query(Area)

    if not include_hidden:
        query = query.filter(Area.is_public == True)

    areas = query.order_by(Area.name).all()

    return AreaListResponse(
        items=[area_to_response(a) for a in areas],
        total=len(areas),
    )


@router.get("/{name}", response_model=AreaResponse)
async def get_area(
    name: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get area details.
    """
    area = db.query(Area).filter(Area.name.ilike(name)).first()

    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area non trovata",
        )

    return area_to_response(area)


@router.get("/{name}/stats", response_model=AreaStatsResponse)
async def get_area_stats(
    name: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed area statistics.
    """
    area = db.query(Area).filter(Area.name.ilike(name)).first()

    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area non trovata",
        )

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Count unique posters
    unique_posters = (
        db.query(func.count(func.distinct(Message.sender_key)))
        .filter(Message.area_id == area.id)
        .scalar()
    )

    # Messages today
    messages_today = (
        db.query(Message)
        .filter(Message.area_id == area.id, Message.timestamp >= today_start)
        .count()
    )

    # Messages this week
    messages_week = (
        db.query(Message)
        .filter(Message.area_id == area.id, Message.timestamp >= week_ago)
        .count()
    )

    # Top posters
    top_posters_query = (
        db.query(
            Message.sender_key,
            func.count(Message.id).label("count"),
        )
        .filter(Message.area_id == area.id)
        .group_by(Message.sender_key)
        .order_by(func.count(Message.id).desc())
        .limit(5)
        .all()
    )

    top_posters = []
    for sender_key, count in top_posters_query:
        user = db.query(User).filter(User.public_key == sender_key).first()
        top_posters.append({
            "public_key": sender_key,
            "nickname": user.nickname if user else sender_key[:8],
            "message_count": count,
        })

    return AreaStatsResponse(
        name=area.name,
        message_count=area.message_count,
        unique_posters=unique_posters or 0,
        messages_today=messages_today,
        messages_week=messages_week,
        last_post_at=area.last_post_at.isoformat() if area.last_post_at else None,
        top_posters=top_posters,
    )


@router.post("", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    request: AreaCreateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new area.
    """
    # Check if area exists
    existing = db.query(Area).filter(Area.name.ilike(request.name)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Area già esistente",
        )

    # Create area
    area = Area(
        name=request.name.lower(),
        description=request.description,
        is_public=request.is_public,
        is_readonly=request.is_readonly,
    )
    db.add(area)

    # Log event
    db.add(ActivityLog.log(
        EventType.AREA_CREATED,
        details=f"Area '{area.name}' created by admin",
    ))

    db.commit()
    db.refresh(area)

    return area_to_response(area)


@router.patch("/{name}", response_model=AreaResponse)
async def update_area(
    name: str,
    request: AreaUpdateRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Update an area.
    """
    area = db.query(Area).filter(Area.name.ilike(name)).first()

    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area non trovata",
        )

    # Update fields
    changes = []
    if request.description is not None:
        area.description = request.description
        changes.append("description")
    if request.is_public is not None:
        area.is_public = request.is_public
        changes.append(f"is_public={request.is_public}")
    if request.is_readonly is not None:
        area.is_readonly = request.is_readonly
        changes.append(f"is_readonly={request.is_readonly}")

    if changes:
        db.add(ActivityLog.log(
            EventType.AREA_MODIFIED,
            details=f"Area '{area.name}' modified: {', '.join(changes)}",
        ))

    db.commit()
    db.refresh(area)

    return area_to_response(area)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    name: str,
    delete_messages: bool = Query(default=True, description="Delete all messages in area"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete an area.

    Cannot delete protected areas (generale, general).
    """
    area = db.query(Area).filter(Area.name.ilike(name)).first()

    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area non trovata",
        )

    # Check if protected
    if area.name.lower() in PROTECTED_AREAS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi eliminare l'area predefinita",
        )

    # Count and optionally delete messages
    message_count = db.query(Message).filter(Message.area_id == area.id).count()

    if delete_messages:
        db.query(Message).filter(Message.area_id == area.id).delete()

    # Log event
    db.add(ActivityLog.log(
        EventType.AREA_DELETED,
        details=f"Area '{area.name}' deleted with {message_count} messages",
    ))

    # Delete area
    db.delete(area)
    db.commit()


@router.get("/{name}/messages")
async def get_area_messages(
    name: str,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get messages in an area.
    """
    area = db.query(Area).filter(Area.name.ilike(name)).first()

    if not area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area non trovata",
        )

    # Get total count
    total = db.query(Message).filter(Message.area_id == area.id).count()

    # Get messages
    offset = (page - 1) * per_page
    messages = (
        db.query(Message)
        .filter(Message.area_id == area.id)
        .order_by(Message.timestamp.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Build response
    items = []
    for msg in messages:
        user = db.query(User).filter(User.public_key == msg.sender_key).first()
        items.append({
            "id": msg.id,
            "sender_key": msg.sender_key,
            "sender_nickname": user.nickname if user else None,
            "body": msg.body,
            "parent_id": msg.parent_id,
            "reply_count": msg.reply_count,
            "created_at": msg.timestamp.isoformat() if msg.timestamp else None,
        })

    pages = (total + per_page - 1) // per_page

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }
