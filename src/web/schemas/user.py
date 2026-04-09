"""
User schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """BBS user response schema."""

    public_key: str
    nickname: Optional[str]
    role: str  # "admin", "moderator", "user"
    is_banned: bool
    is_muted: bool
    is_kicked: bool
    kick_remaining_minutes: Optional[int]
    ban_reason: Optional[str]
    mute_reason: Optional[str]
    kick_reason: Optional[str]
    created_at: Optional[str]
    last_seen: Optional[str]
    message_count: int = 0

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list response with pagination info."""

    items: List[UserResponse]
    total: int
    page: int
    per_page: int
    pages: int


class UserStatsResponse(BaseModel):
    """User statistics response."""

    public_key: str
    nickname: Optional[str]
    messages_posted: int
    pms_sent: int
    pms_received: int
    areas_active: List[str]
    first_seen: Optional[str]
    last_seen: Optional[str]


class UserDetailResponse(BaseModel):
    """Detailed user response."""

    public_key: str
    nickname: Optional[str]
    role: str
    is_banned: bool
    is_muted: bool
    is_kicked: bool
    kick_remaining_minutes: Optional[int]
    ban_reason: Optional[str]
    mute_reason: Optional[str]
    kick_reason: Optional[str]
    kicked_until: Optional[str]
    created_at: Optional[str]
    last_seen: Optional[str]
    stats: UserStatsResponse


class BanUserRequest(BaseModel):
    """Ban user request schema."""

    reason: Optional[str] = Field(None, max_length=200)
    notify_user: bool = False
    delete_messages: bool = False


class MuteUserRequest(BaseModel):
    """Mute user request schema."""

    reason: Optional[str] = Field(None, max_length=200)


class KickUserRequest(BaseModel):
    """Kick user request schema."""

    minutes: int = Field(default=30, ge=1, le=1440)
    reason: Optional[str] = Field(None, max_length=200)


class PromoteUserRequest(BaseModel):
    """Promote user request schema."""

    to_admin: bool = False  # If False, promote to moderator


class UserFilterParams(BaseModel):
    """User filter parameters."""

    role: Optional[str] = Field(None, pattern="^(admin|moderator|user)$")
    status: Optional[str] = Field(None, pattern="^(active|banned|muted|kicked)$")
    search: Optional[str] = Field(None, max_length=100)
    active_hours: Optional[int] = Field(None, ge=1, le=720)
