"""
Common schemas for MeshCore BBS web API.

MIT License - Copyright (c) 2026 MeshBBS Contributors
"""

from typing import Generic, TypeVar, Optional, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: List[T]
    total: int
    page: int
    per_page: int
    pages: int

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        per_page: int,
    ) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    code: Optional[str] = None
    field: Optional[str] = None


class SuccessResponse(BaseModel):
    """Success response schema."""

    message: str
    data: Optional[dict] = None


class BulkActionRequest(BaseModel):
    """Request for bulk actions."""

    ids: List[int] = Field(..., min_length=1, max_length=100)


class BulkActionResponse(BaseModel):
    """Response for bulk actions."""

    success_count: int
    failed_count: int
    errors: List[str] = []


class DateRangeParams(BaseModel):
    """Date range filter parameters."""

    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    end_date: Optional[str] = Field(None, description="End date (ISO format)")
