"""Parent and guardian authorization helpers for future Parent Portal endpoints."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.core.security.context import RequestContext
from app.core.security.dependencies import get_authentication_service, get_request_context
from app.modules.authentication.exceptions import AuthenticationError
from app.modules.authentication.service import AuthenticationService


def require_guardian_student_link(student_id: UUID) -> Callable[..., RequestContext]:
    """Return a dependency that requires the active parent context to own a student link."""

    def dependency(
        context: RequestContext = Depends(get_request_context),
        service: AuthenticationService = Depends(get_authentication_service),
    ) -> RequestContext:
        try:
            service.validate_guardian_student_link(context=context, student_id=student_id)
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.") from exc
        return context

    return dependency
