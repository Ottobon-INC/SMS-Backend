"""Common Pydantic schema primitives shared across backend modules."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Simple message response for non-domain API responses."""

    message: str
