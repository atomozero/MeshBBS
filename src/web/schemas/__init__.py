"""
Pydantic schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from .common import (
    PaginationParams,
    PaginatedResponse,
    ErrorResponse,
    SuccessResponse,
)
from .user import UserResponse, UserListResponse, UserStatsResponse
from .area import AreaResponse, AreaCreateRequest, AreaUpdateRequest
from .message import MessageResponse, MessageListResponse
from .stats import DashboardStats, SystemStatus, ActivityItem

__all__ = [
    "PaginationParams",
    "PaginatedResponse",
    "ErrorResponse",
    "SuccessResponse",
    "UserResponse",
    "UserListResponse",
    "UserStatsResponse",
    "AreaResponse",
    "AreaCreateRequest",
    "AreaUpdateRequest",
    "MessageResponse",
    "MessageListResponse",
    "DashboardStats",
    "SystemStatus",
    "ActivityItem",
]
