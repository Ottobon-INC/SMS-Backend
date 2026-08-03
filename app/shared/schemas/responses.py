"""Common API response envelopes shared across backend modules."""

from pydantic import BaseModel


class ErrorPayload(BaseModel):
    """Structured API error payload."""

    code: str
    message: str
    correlation_id: str | None = None
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    """Structured API error response."""

    error: ErrorPayload
