"""
Dashboard API endpoints for MeshCore BBS web interface.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from web.dependencies import get_db, get_current_admin
from web.auth.models import AdminUser
from web.schemas.stats import (
    DashboardStats,
    UserStats,
    MessageStats,
    AreaStats,
    PrivateMessageStats,
    SystemStatus,
    ActivityItem,
    ActivityFeedResponse,
    ActivityChartResponse,
)
from bbs.models.user import User
from bbs.models.message import Message
from bbs.models.area import Area
from bbs.models.private_message import PrivateMessage
from bbs.models.activity_log import ActivityLog, EventType
from web import __version__ as web_version
from meshcore.state import get_state_manager


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# Event type to icon/color mapping
EVENT_ICONS = {
    EventType.USER_FIRST_SEEN.value: ("👤", "blue"),
    EventType.USER_NICKNAME_SET.value: ("✏️", "gray"),
    EventType.USER_BANNED.value: ("🚫", "red"),
    EventType.USER_UNBANNED.value: ("✅", "green"),
    EventType.USER_MUTED.value: ("🔇", "orange"),
    EventType.USER_UNMUTED.value: ("🔊", "green"),
    EventType.USER_KICKED.value: ("👢", "orange"),
    EventType.USER_UNKICKED.value: ("✅", "green"),
    EventType.USER_PROMOTED.value: ("⬆️", "blue"),
    EventType.USER_DEMOTED.value: ("⬇️", "gray"),
    EventType.MESSAGE_POSTED.value: ("💬", "blue"),
    EventType.MESSAGE_DELETED.value: ("🗑️", "red"),
    EventType.PRIVATE_MSG_SENT.value: ("✉️", "purple"),
    EventType.AREA_CREATED.value: ("📁", "green"),
    EventType.AREA_DELETED.value: ("🗑️", "red"),
    EventType.AREA_MODIFIED.value: ("📝", "gray"),
}


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get dashboard statistics.

    Returns counts for users, messages, areas, and system status.
    """
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # User stats
    total_users = db.query(User).count()
    active_24h = db.query(User).filter(
        User.last_seen >= now - timedelta(hours=24)
    ).count()
    active_7d = db.query(User).filter(User.last_seen >= week_ago).count()
    banned_users = db.query(User).filter(User.is_banned == True).count()
    muted_users = db.query(User).filter(User.is_muted == True).count()
    kicked_users = db.query(User).filter(
        User.kicked_until != None,
        User.kicked_until > now,
    ).count()
    admin_users = db.query(User).filter(User.is_admin == True).count()
    mod_users = db.query(User).filter(
        User.is_moderator == True,
        User.is_admin == False,
    ).count()

    user_stats = UserStats(
        total=total_users,
        active_24h=active_24h,
        active_7d=active_7d,
        banned=banned_users,
        muted=muted_users,
        kicked=kicked_users,
        admins=admin_users,
        moderators=mod_users,
    )

    # Message stats
    total_messages = db.query(Message).count()
    messages_today = db.query(Message).filter(
        Message.timestamp >= today_start
    ).count()
    messages_week = db.query(Message).filter(
        Message.timestamp >= week_ago
    ).count()
    messages_month = db.query(Message).filter(
        Message.timestamp >= month_ago
    ).count()

    message_stats = MessageStats(
        total=total_messages,
        today=messages_today,
        week=messages_week,
        month=messages_month,
    )

    # Area stats
    total_areas = db.query(Area).count()
    public_areas = db.query(Area).filter(Area.is_public == True).count()
    readonly_areas = db.query(Area).filter(Area.is_readonly == True).count()

    area_stats = AreaStats(
        total=total_areas,
        public=public_areas,
        readonly=readonly_areas,
    )

    # PM stats
    total_pms = db.query(PrivateMessage).count()
    pms_today = db.query(PrivateMessage).filter(
        PrivateMessage.timestamp >= today_start
    ).count()
    unread_pms = db.query(PrivateMessage).filter(
        PrivateMessage.is_read == False
    ).count()

    pm_stats = PrivateMessageStats(
        total=total_pms,
        today=pms_today,
        unread=unread_pms,
    )

    # System status
    from utils.config import get_config
    config = get_config()

    # Get database size
    db_path = config.database_path
    db_size = 0
    if os.path.exists(db_path):
        db_size = os.path.getsize(db_path)

    # Calculate uptime (approximate - from process start)
    import time
    uptime = int(time.time() - time.monotonic())

    # Get real connection state
    state_manager = get_state_manager()
    radio_connected = state_manager.is_connected
    radio_port = config.serial_port
    if state_manager.state.radio_info.port:
        radio_port = state_manager.state.radio_info.port

    system_status = SystemStatus(
        uptime_seconds=uptime,
        db_size_bytes=db_size,
        db_path=db_path,
        radio_connected=radio_connected,
        radio_port=radio_port,
        python_version=sys.version.split()[0],
        bbs_version="1.3.0",
        web_version=web_version,
    )

    return DashboardStats(
        users=user_stats,
        messages=message_stats,
        areas=area_stats,
        private_messages=pm_stats,
        system=system_status,
    )


@router.get("/activity", response_model=ActivityFeedResponse)
async def get_activity_feed(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get recent activity feed.

    Returns the most recent system events.
    """
    # Get total count
    total = db.query(ActivityLog).count()

    # Get activity logs
    logs = (
        db.query(ActivityLog)
        .order_by(ActivityLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Convert to response format
    items = []
    for log in logs:
        icon, color = EVENT_ICONS.get(log.event_type, ("📌", "gray"))

        # Get user nickname if available
        nickname = None
        if log.user_key:
            user = db.query(User).filter(User.public_key == log.user_key).first()
            if user:
                nickname = user.nickname

        items.append(ActivityItem(
            id=log.id,
            event_type=log.event_type,
            user_key=log.user_key,
            user_nickname=nickname,
            details=log.details,
            timestamp=log.timestamp.isoformat() if log.timestamp else None,
            icon=icon,
            color=color,
        ))

    return ActivityFeedResponse(items=items, total=total)


@router.get("/chart", response_model=ActivityChartResponse)
async def get_activity_chart(
    period: str = Query(default="7d", pattern="^(7d|30d|90d)$"),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get activity chart data.

    Returns daily message and user counts for the specified period.
    """
    # Determine date range
    days = {"7d": 7, "30d": 30, "90d": 90}[period]
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    labels = []
    messages_data = []
    users_data = []

    # Generate data for each day
    for i in range(days):
        day = start_date + timedelta(days=i + 1)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Format label
        labels.append(day_start.strftime("%d/%m"))

        # Count messages for this day
        msg_count = db.query(Message).filter(
            Message.timestamp >= day_start,
            Message.timestamp < day_end,
        ).count()
        messages_data.append(msg_count)

        # Count active users for this day
        user_count = db.query(User).filter(
            User.last_seen >= day_start,
            User.last_seen < day_end,
        ).count()
        users_data.append(user_count)

    return ActivityChartResponse(
        labels=labels,
        messages=messages_data,
        users=users_data,
        period=period,
    )


@router.get("/top-users")
async def get_top_users(
    limit: int = Query(default=10, ge=1, le=50),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Get top users by message count.
    """
    # Query users with message count
    results = (
        db.query(
            User.public_key,
            User.nickname,
            User.last_seen,
            func.count(Message.id).label("message_count"),
        )
        .outerjoin(Message, User.public_key == Message.sender_key)
        .group_by(User.public_key)
        .order_by(func.count(Message.id).desc())
        .limit(limit)
        .all()
    )

    return {
        "items": [
            {
                "public_key": r.public_key,
                "nickname": r.nickname or r.public_key[:8],
                "message_count": r.message_count,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in results
        ]
    }
