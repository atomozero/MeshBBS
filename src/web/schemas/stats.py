"""
Statistics schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional, List
from pydantic import BaseModel


class UserStats(BaseModel):
    """User statistics."""

    total: int
    active_24h: int
    active_7d: int
    banned: int
    muted: int
    kicked: int
    admins: int
    moderators: int


class MessageStats(BaseModel):
    """Message statistics."""

    total: int
    today: int
    week: int
    month: int


class AreaStats(BaseModel):
    """Area statistics."""

    total: int
    public: int
    readonly: int


class PrivateMessageStats(BaseModel):
    """Private message statistics."""

    total: int
    today: int
    unread: int


class SystemStatus(BaseModel):
    """System status information."""

    uptime_seconds: int
    db_size_bytes: int
    db_path: str
    radio_connected: bool
    radio_port: Optional[str]
    python_version: str
    bbs_version: str
    web_version: str


class DashboardStats(BaseModel):
    """Dashboard statistics response."""

    users: UserStats
    messages: MessageStats
    areas: AreaStats
    private_messages: PrivateMessageStats
    system: SystemStatus


class ActivityItem(BaseModel):
    """Activity feed item."""

    id: int
    event_type: str
    user_key: Optional[str]
    user_nickname: Optional[str]
    details: Optional[str]
    timestamp: str
    icon: str  # Emoji or icon name
    color: str  # CSS color class


class ActivityFeedResponse(BaseModel):
    """Activity feed response."""

    items: List[ActivityItem]
    total: int


class ChartDataPoint(BaseModel):
    """Chart data point."""

    label: str
    value: int


class ActivityChartResponse(BaseModel):
    """Activity chart data response."""

    labels: List[str]
    messages: List[int]
    users: List[int]
    period: str  # "7d", "30d", "90d"


class TopUsersResponse(BaseModel):
    """Top users response."""

    items: List[dict]  # [{nickname, messages_count, last_seen}]


class RetentionStats(BaseModel):
    """Retention policy statistics."""

    pm_retention_days: int
    log_retention_days: int
    expired_pms: int
    expired_logs: int
    last_cleanup: Optional[str]
    next_cleanup: Optional[str]


class RateLimitStats(BaseModel):
    """Rate limiter statistics."""

    enabled: bool
    min_interval: float
    max_per_minute: int
    block_duration: int
    currently_blocked: int
    total_blocks_today: int
