from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str | None = None
    details: dict[str, object] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
