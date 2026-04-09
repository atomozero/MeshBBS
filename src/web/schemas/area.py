"""
Area schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class AreaResponse(BaseModel):
    """Area response schema."""

    id: int
    name: str
    description: Optional[str]
    is_public: bool
    is_readonly: bool
    message_count: int
    created_at: Optional[str]
    last_post_at: Optional[str]

    class Config:
        from_attributes = True


class AreaListResponse(BaseModel):
    """Area list response."""

    items: List[AreaResponse]
    total: int


class AreaCreateRequest(BaseModel):
    """Create area request schema."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=32,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_-]*$",
        description="Area name (letters, numbers, underscore, hyphen)",
    )
    description: Optional[str] = Field(None, max_length=200)
    is_public: bool = True
    is_readonly: bool = False


class AreaUpdateRequest(BaseModel):
    """Update area request schema."""

    description: Optional[str] = Field(None, max_length=200)
    is_public: Optional[bool] = None
    is_readonly: Optional[bool] = None


class AreaStatsResponse(BaseModel):
    """Area statistics response."""

    name: str
    message_count: int
    unique_posters: int
    messages_today: int
    messages_week: int
    last_post_at: Optional[str]
    top_posters: List[dict]
