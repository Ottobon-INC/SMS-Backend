"""Authentication API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.security.dependencies import get_authenticated_principal, get_authentication_service
from app.core.security.jwt import AuthenticatedPrincipal
from app.modules.authentication.exceptions import (
    AuthenticationError,
    CredentialStoreNotConfiguredError,
    SignupRequestStoreNotConfiguredError,
)
from app.modules.authentication.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    SelectContextRequest,
    SignupRequestPayload,
    SignupRequestResponse,
)
from app.modules.authentication.service import AuthenticationService

router = APIRouter(prefix="/auth", tags=["authentication"])


def _auth_error(exc: AuthenticationError) -> HTTPException:
    if isinstance(exc, CredentialStoreNotConfiguredError | SignupRequestStoreNotConfiguredError):
        return HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc))
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    assignment_id: UUID | None = Header(default=None, alias="X-Access-Assignment-ID"),
    service: AuthenticationService = Depends(get_authentication_service),
) -> LoginResponse:
    try:
        return service.authenticate_with_password(
            login_identifier=request.login_identifier,
            password=request.password,
            requested_assignment_id=assignment_id,
        )
    except AuthenticationError as exc:
        raise _auth_error(exc) from exc


@router.post("/signup-request", response_model=SignupRequestResponse)
def signup_request(
    request: SignupRequestPayload,
    service: AuthenticationService = Depends(get_authentication_service),
) -> SignupRequestResponse:
    try:
        return service.create_signup_request(
            requested_portal=request.requested_portal,
            full_name=request.full_name,
            email=request.email,
            mobile=request.mobile,
            institution_name=request.institution_name,
            branch_name=request.branch_name,
            message=request.message,
        )
    except AuthenticationError as exc:
        raise _auth_error(exc) from exc


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user(
    assignment_id: UUID | None = Header(default=None, alias="X-Access-Assignment-ID"),
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> CurrentUserResponse:
    try:
        return service.resolve_current_user(principal.app_user_id, assignment_id)
    except AuthenticationError as exc:
        raise _auth_error(exc) from exc


@router.get("/contexts", response_model=list[object])
def get_contexts(
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> list[object]:
    try:
        return list(service.resolve_current_user(principal.app_user_id, None).available_contexts)
    except AuthenticationError as exc:
        raise _auth_error(exc) from exc


@router.post("/select-context", response_model=CurrentUserResponse)
def select_context(
    request: SelectContextRequest,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    service: AuthenticationService = Depends(get_authentication_service),
) -> CurrentUserResponse:
    try:
        return service.resolve_current_user(principal.app_user_id, request.assignment_id)
    except AuthenticationError as exc:
        raise _auth_error(exc) from exc
