"""Shared backend Pydantic schemas."""

from app.shared.schemas.common import MessageResponse
from app.shared.schemas.pagination import PaginatedResponse, PaginationParams
from app.shared.schemas.responses import ErrorPayload, ErrorResponse

__all__ = [
    "ErrorPayload",
    "ErrorResponse",
    "MessageResponse",
    "PaginatedResponse",
    "PaginationParams",
]
