"""
Message schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Message response schema."""

    id: int
    area_name: str
    sender_key: str
    sender_nickname: Optional[str]
    body: str
    parent_id: Optional[int]
    reply_count: int
    created_at: Optional[str]
    hops: Optional[int]
    rssi: Optional[int]

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Message list response with pagination."""

    items: List[MessageResponse]
    total: int
    page: int
    per_page: int
    pages: int


class MessageDetailResponse(BaseModel):
    """Detailed message response with thread."""

    id: int
    area_name: str
    sender_key: str
    sender_nickname: Optional[str]
    body: str
    parent_id: Optional[int]
    reply_count: int
    created_at: Optional[str]
    hops: Optional[int]
    rssi: Optional[int]
    replies: List["MessageResponse"]


class MessageFilterParams(BaseModel):
    """Message filter parameters."""

    area: Optional[str] = Field(None, description="Filter by area name")
    sender: Optional[str] = Field(None, description="Filter by sender key or nickname")
    search: Optional[str] = Field(None, max_length=100, description="Search in body")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")


class PrivateMessageResponse(BaseModel):
    """Private message response schema."""

    id: int
    sender_key: str
    sender_nickname: Optional[str]
    recipient_key: str
    recipient_nickname: Optional[str]
    body: str
    is_read: bool
    created_at: Optional[str]

    class Config:
        from_attributes = True


class PrivateMessageListResponse(BaseModel):
    """Private message list response."""

    items: List[PrivateMessageResponse]
    total: int
    page: int
    per_page: int
    pages: int
