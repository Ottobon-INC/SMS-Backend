"""Authentication API schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AuthenticatedUserResponse(BaseModel):
    id: UUID
    display_name: str
    email: str | None
    status: str
    account_category: str


class TenantSummary(BaseModel):
    id: UUID
    name: str
    status: str


class BranchSummary(BaseModel):
    id: UUID
    name: str
    status: str


class RoleSummary(BaseModel):
    code: str
    label: str


class AccessContextSummary(BaseModel):
    assignment_id: UUID
    tenant: TenantSummary | None = None
    branch: BranchSummary | None = None
    role: RoleSummary
    scope_type: str
    enabled_modules: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class ActiveContextResponse(BaseModel):
    assignment_id: UUID
    tenant_id: UUID | None = None
    branch_id: UUID | None = None
    role_codes: list[str]
    permissions: list[str]
    enabled_modules: list[str]
    scope_type: str


class CurrentUserResponse(BaseModel):
    user: AuthenticatedUserResponse
    available_contexts: list[AccessContextSummary]
    active_context: ActiveContextResponse | None = None


class LoginRequest(BaseModel):
    login_identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    portal: str | None = Field(default=None, max_length=40)


class LoginResponse(CurrentUserResponse):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class SignupRequestPayload(BaseModel):
    requested_portal: str = Field(min_length=1, max_length=40)
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    mobile: str | None = Field(default=None, max_length=30)
    institution_name: str | None = Field(default=None, max_length=200)
    branch_name: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)


class SignupRequestResponse(BaseModel):
    request_id: UUID
    status: str = "PENDING"


class SelectContextRequest(BaseModel):
    assignment_id: UUID
