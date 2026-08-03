"""Pagination schemas shared by backend API modules."""

from typing import TypeVar

from pydantic import BaseModel, Field

TItem = TypeVar("TItem")


class PaginationParams(BaseModel):
    """Validated pagination query parameters."""

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class PaginatedResponse[TItem](BaseModel):
    """Generic paginated response envelope."""

    items: list[TItem]
    total: int
    page: int
    page_size: int
