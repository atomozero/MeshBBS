"""
Messages API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from web.schemas.message import (
    MessageResponse,
    MessageListResponse,
    MessageDetailResponse,
    PrivateMessageResponse,
    PrivateMessageListResponse,
)
from web.schemas.common import SuccessResponse, BulkActionRequest, BulkActionResponse
from bbs.models.message import Message
from bbs.models.private_message import PrivateMessage
from bbs.models.area import Area
from bbs.models.user import User
from bbs.models.activity_log import ActivityLog, EventType


router = APIRouter(prefix="/messages", tags=["Messages"])


def message_to_response(msg: Message, db: Session) -> MessageResponse:
    """Convert Message model to response schema."""
    user = db.query(User).filter(User.public_key == msg.sender_key).first()
    area = db.query(Area).filter(Area.id == msg.area_id).first()

    return MessageResponse(
        id=msg.id,
        area_name=area.name if area else "unknown",
        sender_key=msg.sender_key,
        sender_nickname=user.nickname if user else None,
        body=msg.body,
        parent_id=msg.parent_id,
        reply_count=msg.reply_count,
        created_at=msg.timestamp.isoformat() if msg.timestamp else None,
        hops=msg.hops,
        rssi=msg.rssi,
    )


@router.get("", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    area: Optional[str] = Query(default=None, description="Filter by area name"),
    sender: Optional[str] = Query(default=None, description="Filter by sender"),
    search: Optional[str] = Query(default=None, max_length=100, description="Search in body"),
    start_date: Optional[str] = Query(default=None, description="Start date (ISO)"),
    end_date: Optional[str] = Query(default=None, description="End date (ISO)"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List messages with filtering and pagination.
    """
    query = db.query(Message)

    # Filter by area
    if area:
        area_obj = db.query(Area).filter(Area.name.ilike(area)).first()
        if area_obj:
            query = query.filter(Message.area_id == area_obj.id)
        else:
            # Return empty if area not found
            return MessageListResponse(items=[], total=0, page=page, per_page=per_page, pages=0)

    # Filter by sender
    if sender:
        user = db.query(User).filter(
            or_(
                User.nickname.ilike(sender),
                User.public_key.startswith(sender),
            )
        ).first()
        if user:
            query = query.filter(Message.sender_key == user.public_key)
        else:
            query = query.filter(Message.sender_key.startswith(sender))

    # Search in body
    if search:
        query = query.filter(Message.body.ilike(f"%{search}%"))

    # Date filters
    if start_date:
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            query = query.filter(Message.timestamp >= start)
        except ValueError:
            pass

    if end_date:
        try:
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            query = query.filter(Message.timestamp <= end)
        except ValueError:
            pass

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    messages = (
        query.order_by(Message.timestamp.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Convert to response
    items = [message_to_response(msg, db) for msg in messages]
    pages = (total + per_page - 1) // per_page

    return MessageListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{message_id}", response_model=MessageDetailResponse)
async def get_message(
    message_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get message details with replies.
    """
    msg = db.query(Message).filter(Message.id == message_id).first()

    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messaggio non trovato",
        )

    user = db.query(User).filter(User.public_key == msg.sender_key).first()
    area = db.query(Area).filter(Area.id == msg.area_id).first()

    # Get replies
    replies = db.query(Message).filter(Message.parent_id == msg.id).order_by(Message.timestamp).all()
    reply_responses = [message_to_response(r, db) for r in replies]

    return MessageDetailResponse(
        id=msg.id,
        area_name=area.name if area else "unknown",
        sender_key=msg.sender_key,
        sender_nickname=user.nickname if user else None,
        body=msg.body,
        parent_id=msg.parent_id,
        reply_count=msg.reply_count,
        created_at=msg.timestamp.isoformat() if msg.timestamp else None,
        hops=msg.hops,
        rssi=msg.rssi,
        replies=reply_responses,
    )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a message.

    Also deletes all replies if it's a parent message.
    """
    msg = db.query(Message).filter(Message.id == message_id).first()

    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messaggio non trovato",
        )

    # Delete replies first
    deleted_replies = db.query(Message).filter(Message.parent_id == msg.id).delete()

    # Update area message count
    area = db.query(Area).filter(Area.id == msg.area_id).first()
    if area:
        area.message_count = max(0, area.message_count - 1 - deleted_replies)

    # Log event
    db.add(ActivityLog.log(
        EventType.MESSAGE_POSTED,  # Using same event for delete (could add MESSAGE_DELETED)
        user_key=msg.sender_key,
        details=f"Message #{msg.id} deleted by admin (with {deleted_replies} replies)",
    ))

    # Delete message
    db.delete(msg)
    db.commit()


@router.post("/bulk-delete", response_model=BulkActionResponse)
async def bulk_delete_messages(
    request: BulkActionRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete multiple messages.
    """
    success_count = 0
    failed_count = 0
    errors = []

    for msg_id in request.ids:
        msg = db.query(Message).filter(Message.id == msg_id).first()
        if msg:
            # Delete replies
            db.query(Message).filter(Message.parent_id == msg.id).delete()
            db.delete(msg)
            success_count += 1
        else:
            failed_count += 1
            errors.append(f"Messaggio #{msg_id} non trovato")

    db.commit()

    return BulkActionResponse(
        success_count=success_count,
        failed_count=failed_count,
        errors=errors,
    )


# Private messages endpoints
@router.get("/private", response_model=PrivateMessageListResponse)
async def list_private_messages(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user_key: Optional[str] = Query(default=None, description="Filter by user (sender or recipient)"),
    unread_only: bool = Query(default=False, description="Show only unread"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    List private messages (admin view).
    """
    query = db.query(PrivateMessage)

    # Filter by user
    if user_key:
        query = query.filter(
            or_(
                PrivateMessage.sender_key == user_key,
                PrivateMessage.recipient_key == user_key,
            )
        )

    # Filter unread only
    if unread_only:
        query = query.filter(PrivateMessage.is_read == False)

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * per_page
    messages = (
        query.order_by(PrivateMessage.timestamp.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # Convert to response
    items = []
    for pm in messages:
        sender = db.query(User).filter(User.public_key == pm.sender_key).first()
        recipient = db.query(User).filter(User.public_key == pm.recipient_key).first()

        items.append(PrivateMessageResponse(
            id=pm.id,
            sender_key=pm.sender_key,
            sender_nickname=sender.nickname if sender else None,
            recipient_key=pm.recipient_key,
            recipient_nickname=recipient.nickname if recipient else None,
            body=pm.body,
            is_read=pm.is_read,
            created_at=pm.timestamp.isoformat() if pm.timestamp else None,
        ))

    pages = (total + per_page - 1) // per_page

    return PrivateMessageListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.delete("/private/{pm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_private_message(
    pm_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a private message.
    """
    pm = db.query(PrivateMessage).filter(PrivateMessage.id == pm_id).first()

    if not pm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Messaggio privato non trovato",
        )

    db.delete(pm)
    db.commit()
