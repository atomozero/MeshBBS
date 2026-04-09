"""
Users API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from web.schemas.user import (
    UserResponse,
    UserListResponse,
    UserDetailResponse,
    UserStatsResponse,
    BanUserRequest,
    MuteUserRequest,
    KickUserRequest,
    PromoteUserRequest,
    UserFilterParams,
)
from web.schemas.common import SuccessResponse
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType
from bbs.repositories.user_repository import UserRepository


router = APIRouter(prefix="/users", tags=["Users"])


def user_to_response(user: User, message_count: int = 0) -> UserResponse:
    """Convert User model to response schema."""
    role = "user"
    if user.is_admin:
        role = "admin"
    elif user.is_moderator:
        role = "moderator"

    return UserResponse(
        public_key=user.public_key,
        nickname=user.nickname,
        role=role,
        is_banned=user.is_banned,
        is_muted=user.is_muted,
        is_kicked=user.is_kicked,
        kick_remaining_minutes=user.kick_remaining_minutes if user.is_kicked else None,
        ban_reason=user.ban_reason,
        mute_reason=user.mute_reason,
        kick_reason=user.kick_reason,
        created_at=user.first_seen.isoformat() if user.first_seen else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
        message_count=message_count,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="last_seen", pattern="^(last_seen|created_at|nickname|messages)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    role: Optional[str] = Query(default=None, pattern="^(admin|moderator|user)$"),
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(active|banned|muted|kicked)$"),
    search: Optional[str] = Query(default=None, max_length=100),
    active_hours: Optional[int] = Query(default=None, ge=1, le=720),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List BBS users with filtering and pagination.
    """
    # Base query with message count
    query = db.query(
        User,
        func.count(Message.id).label("message_count"),
    ).outerjoin(Message, User.public_key == Message.sender_key).group_by(User.public_key)

    # Apply role filter
    if role == "admin":
        query = query.filter(User.is_admin == True)
    elif role == "moderator":
        query = query.filter(User.is_moderator == True, User.is_admin == False)
    elif role == "user":
        query = query.filter(User.is_admin == False, User.is_moderator == False)

    # Apply status filter
    if status_filter == "banned":
        query = query.filter(User.is_banned == True)
    elif status_filter == "muted":
        query = query.filter(User.is_muted == True)
    elif status_filter == "kicked":
        query = query.filter(User.kicked_until != None, User.kicked_until > datetime.utcnow())
    elif status_filter == "active":
        query = query.filter(
            User.is_banned == False,
            User.is_muted == False,
            or_(User.kicked_until == None, User.kicked_until <= datetime.utcnow()),
        )

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                User.nickname.ilike(search_pattern),
                User.public_key.ilike(search_pattern),
            )
        )

    # Apply active hours filter
    if active_hours:
        cutoff = datetime.utcnow() - timedelta(hours=active_hours)
        query = query.filter(User.last_seen >= cutoff)

    # Get total count (before pagination)
    total = query.count()

    # Apply sorting
    if sort_by == "messages":
        order_col = func.count(Message.id)
    else:
        order_col = getattr(User, sort_by, User.last_seen)

    if sort_order == "desc":
        query = query.order_by(order_col.desc())
    else:
        query = query.order_by(order_col.asc())

    # Apply pagination
    offset = (page - 1) * per_page
    results = query.offset(offset).limit(per_page).all()

    # Convert to response
    items = [user_to_response(user, msg_count) for user, msg_count in results]
    pages = (total + per_page - 1) // per_page

    return UserListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{public_key}", response_model=UserDetailResponse)
async def get_user(
    public_key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed user information.
    """
    user = db.query(User).filter(User.public_key == public_key).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    # Get statistics
    messages_posted = db.query(Message).filter(Message.sender_key == public_key).count()
    pms_sent = db.query(PrivateMessage).filter(PrivateMessage.sender_key == public_key).count()
    pms_received = db.query(PrivateMessage).filter(PrivateMessage.recipient_key == public_key).count()

    # Get areas user is active in
    active_areas = (
        db.query(Message.area_id)
        .filter(Message.sender_key == public_key)
        .distinct()
        .all()
    )
    from bbs.models.area import Area
    area_names = []
    for (area_id,) in active_areas:
        area = db.query(Area).filter(Area.id == area_id).first()
        if area:
            area_names.append(area.name)

    role = "user"
    if user.is_admin:
        role = "admin"
    elif user.is_moderator:
        role = "moderator"

    stats = UserStatsResponse(
        public_key=user.public_key,
        nickname=user.nickname,
        messages_posted=messages_posted,
        pms_sent=pms_sent,
        pms_received=pms_received,
        areas_active=area_names,
        first_seen=user.first_seen.isoformat() if user.first_seen else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
    )

    return UserDetailResponse(
        public_key=user.public_key,
        nickname=user.nickname,
        role=role,
        is_banned=user.is_banned,
        is_muted=user.is_muted,
        is_kicked=user.is_kicked,
        kick_remaining_minutes=user.kick_remaining_minutes if user.is_kicked else None,
        ban_reason=user.ban_reason,
        mute_reason=user.mute_reason,
        kick_reason=user.kick_reason,
        kicked_until=user.kicked_until.isoformat() if user.kicked_until else None,
        created_at=user.first_seen.isoformat() if user.first_seen else None,
        last_seen=user.last_seen.isoformat() if user.last_seen else None,
        stats=stats,
    )


@router.post("/{public_key}/ban", response_model=SuccessResponse)
async def ban_user(
    public_key: str,
    request: BanUserRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Ban a user.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi bannare un admin",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente già bannato",
        )

    # Ban user
    repo.ban_user(public_key, request.reason)

    # Delete messages if requested
    if request.delete_messages:
        deleted = db.query(Message).filter(Message.sender_key == public_key).delete()
        db.add(ActivityLog.log(
            EventType.MESSAGE_POSTED,
            user_key=public_key,
            details=f"Deleted {deleted} messages due to ban",
        ))

    db.commit()

    return SuccessResponse(
        message=f"Utente {user.display_name} bannato",
        data={"deleted_messages": request.delete_messages},
    )


@router.post("/{public_key}/unban", response_model=SuccessResponse)
async def unban_user(
    public_key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Remove ban from a user.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if not user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non è bannato",
        )

    repo.unban_user(public_key)
    db.commit()

    return SuccessResponse(message=f"Ban rimosso per {user.display_name}")


@router.post("/{public_key}/mute", response_model=SuccessResponse)
async def mute_user(
    public_key: str,
    request: MuteUserRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Mute a user (can read but cannot post).
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi mutare un admin",
        )

    if user.is_muted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente già mutato",
        )

    repo.mute_user(public_key, request.reason)
    db.commit()

    return SuccessResponse(message=f"Utente {user.display_name} mutato")


@router.post("/{public_key}/unmute", response_model=SuccessResponse)
async def unmute_user(
    public_key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Remove mute from a user.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if not user.is_muted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non è mutato",
        )

    repo.unmute_user(public_key)
    db.commit()

    return SuccessResponse(message=f"Mute rimosso per {user.display_name}")


@router.post("/{public_key}/kick", response_model=SuccessResponse)
async def kick_user(
    public_key: str,
    request: KickUserRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Temporarily kick a user.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi espellere un admin",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente è bannato, usa unban prima",
        )

    repo.kick_user(public_key, request.minutes, request.reason)
    db.commit()

    return SuccessResponse(
        message=f"Utente {user.display_name} espulso per {request.minutes} minuti"
    )


@router.post("/{public_key}/unkick", response_model=SuccessResponse)
async def unkick_user(
    public_key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Remove kick from a user.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if not user.is_kicked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non è espulso",
        )

    repo.unkick_user(public_key)
    db.commit()

    return SuccessResponse(message=f"Espulsione rimossa per {user.display_name}")


@router.post("/{public_key}/promote", response_model=SuccessResponse)
async def promote_user(
    public_key: str,
    request: PromoteUserRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Promote a user to moderator or admin.
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non puoi promuovere un utente bannato",
        )

    if request.to_admin:
        if user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Utente è già admin",
            )
        repo.promote_to_admin(public_key)
        role = "admin"
    else:
        if user.is_moderator:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Utente è già moderatore o superiore",
            )
        repo.promote_to_moderator(public_key)
        role = "moderatore"

    db.commit()

    return SuccessResponse(message=f"{user.display_name} promosso a {role}")


@router.post("/{public_key}/demote", response_model=SuccessResponse)
async def demote_user(
    public_key: str,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Demote a user (admin -> mod, mod -> user).
    """
    repo = UserRepository(db)
    user = repo.get_by_public_key(public_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    if user.is_admin:
        repo.demote_from_admin(public_key)
        new_role = "moderatore"
    elif user.is_moderator:
        repo.demote_from_moderator(public_key)
        new_role = "utente"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Utente non ha ruoli da rimuovere",
        )

    db.commit()

    return SuccessResponse(message=f"{user.display_name} degradato a {new_role}")


@router.get("/{public_key}/activity")
async def get_user_activity(
    public_key: str,
    limit: int = Query(default=50, ge=1, le=200),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get activity history for a user.
    """
    user = db.query(User).filter(User.public_key == public_key).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utente non trovato",
        )

    logs = (
        db.query(ActivityLog)
        .filter(ActivityLog.user_key == public_key)
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "id": log.id,
                "event_type": log.event_type,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in logs
        ]
    }
