"""Reusable FastAPI authentication and authorization dependencies."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.jwt import (
    AuthenticatedPrincipal,
    TokenVerificationError,
    verify_application_access_token,
)
from app.modules.authentication.repository import AuthenticationRepository
from app.modules.authentication.service import AuthenticationService

bearer_scheme = HTTPBearer(auto_error=False)


def get_authenticated_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )
    try:
        return verify_application_access_token(credentials.credentials)
    except TokenVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def get_authentication_service(session: Session = Depends(get_db_session)) -> AuthenticationService:
    return AuthenticationService(AuthenticationRepository(session))


def get_request_context(
    request: Request,
    assignment_id: UUID | None = Header(default=None, alias="X-Access-Assignment-ID"),
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> RequestContext:
    correlation_id = getattr(request.state, "correlation_id", None)
    if assignment_id is None:
        me = service.resolve_current_user(principal.app_user_id, requested_assignment_id=None)
        if me.active_context is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access context is required.")
        assignment_id = me.active_context.assignment_id
    return service.resolve_request_context(
        app_user_id=principal.app_user_id,
        assignment_id=assignment_id,
        correlation_id=correlation_id,
    )


def require_permission(permission_key: str) -> Callable[[RequestContext], RequestContext]:
    def dependency(context: RequestContext = Depends(get_request_context)) -> RequestContext:
        if permission_key not in context.permission_keys:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        return context

    return dependency


def require_any_permission(permission_keys: set[str]) -> Callable[[RequestContext], RequestContext]:
    def dependency(context: RequestContext = Depends(get_request_context)) -> RequestContext:
        if not context.permission_keys.intersection(permission_keys):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied.")
        return context

    return dependency


def require_enabled_module(module_code: str) -> Callable[[RequestContext], RequestContext]:
    def dependency(context: RequestContext = Depends(get_request_context)) -> RequestContext:
        if module_code not in context.enabled_modules:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Module disabled.")
        return context

    return dependency


def require_platform_scope(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    if context.scope_type != "PLATFORM":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform scope required.")
    return context


def require_tenant_scope(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    if context.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant scope required.")
    return context


def require_branch_scope(context: RequestContext = Depends(get_request_context)) -> RequestContext:
    if context.tenant_id is None or context.branch_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Branch scope required.")
    return context
