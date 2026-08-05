"""Authentication foundation unit tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.config.settings import settings
from app.core.security.context import RequestContext
from app.core.security.jwt import (
    TokenVerificationError,
    create_application_access_token,
    verify_application_access_token,
)
from app.core.security.passwords import generate_password_salt, hash_password, verify_password
from app.modules.authentication.exceptions import (
    ApplicationUserInactiveError,
    ApplicationUserNotMappedError,
    CredentialStoreNotConfiguredError,
    InvalidAccessContextError,
)
from app.modules.authentication.repository import AssignmentRecord, UserRecord
from app.modules.authentication.service import AuthenticationService


def _b64(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _token(secret: str, claims: dict[str, object]) -> str:
    header = _b64({"alg": "HS256", "typ": "JWT"})
    body = _b64(claims)
    signature = hmac.new(secret.encode("utf-8"), f"{header}.{body}".encode(), hashlib.sha256)
    encoded_signature = base64.urlsafe_b64encode(signature.digest()).rstrip(b"=").decode("ascii")
    return f"{header}.{body}.{encoded_signature}"


def test_valid_jwt_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    app_user_id = uuid4()
    monkeypatch.setattr(settings, "app_auth_secret", "test-secret")
    monkeypatch.setattr(settings, "app_auth_issuer", "student-management-backend")
    monkeypatch.setattr(settings, "app_auth_audience", "student-management-frontend")
    token = _token(
        "test-secret",
        {
            "sub": str(app_user_id),
            "exp": int(time.time()) + 300,
            "iss": "student-management-backend",
            "aud": "student-management-frontend",
            "typ": "access",
        },
    )
    principal = verify_application_access_token(token)
    assert principal.app_user_id == app_user_id


def test_application_access_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    app_user_id = uuid4()
    monkeypatch.setattr(settings, "app_auth_secret", "test-secret")
    monkeypatch.setattr(settings, "app_auth_issuer", "student-management-backend")
    monkeypatch.setattr(settings, "app_auth_audience", "student-management-frontend")
    monkeypatch.setattr(settings, "access_token_expire_minutes", 10)
    token = create_application_access_token(app_user_id)
    assert verify_application_access_token(token).app_user_id == app_user_id


def test_expired_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_auth_secret", "test-secret")
    monkeypatch.setattr(settings, "app_auth_issuer", "")
    monkeypatch.setattr(settings, "app_auth_audience", "")
    token = _token("test-secret", {"sub": str(uuid4()), "exp": int(time.time()) - 1, "typ": "access"})
    with pytest.raises(TokenVerificationError, match="expired"):
        verify_application_access_token(token)


def test_invalid_signature_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "app_auth_secret", "correct-secret")
    monkeypatch.setattr(settings, "app_auth_issuer", "")
    monkeypatch.setattr(settings, "app_auth_audience", "")
    token = _token("wrong-secret", {"sub": str(uuid4()), "exp": int(time.time()) + 300, "typ": "access"})
    with pytest.raises(TokenVerificationError, match="signature"):
        verify_application_access_token(token)


class FakeAuthRepository:
    def __init__(self) -> None:
        self.auth_user_id = uuid4()
        self.user_id = uuid4()
        self.assignment_id = uuid4()
        self.role_id = uuid4()
        self.tenant_id = uuid4()
        self.branch_id = uuid4()
        self.guardian_link = False
        self.user_status = "ACTIVE"
        self.login_enabled = True
        self.assignment_status = "ACTIVE"
        self.permissions = ["student.view", "attendance.finalize", "parent.child_view"]
        self.modules: dict[str, Any] = {"modules": ["dashboard", "students", "attendance", "parent-portal"]}
        self.credential_store = False
        self.signup_store = False

    def get_user_by_auth_user_id(self, auth_user_id: UUID) -> UserRecord | None:
        if auth_user_id != self.auth_user_id:
            return None
        return UserRecord(
            id=self.user_id,
            auth_user_id=auth_user_id,
            tenant_id=self.tenant_id,
            account_category="TENANT",
            full_name="Test User",
            email="test@example.com",
            status=self.user_status,
            login_enabled=self.login_enabled,
        )

    def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        if user_id != self.user_id:
            return None
        return UserRecord(
            id=self.user_id,
            auth_user_id=self.auth_user_id,
            tenant_id=self.tenant_id,
            account_category="TENANT",
            full_name="Test User",
            email="test@example.com",
            status=self.user_status,
            login_enabled=self.login_enabled,
        )

    def credential_store_exists(self) -> bool:
        return self.credential_store

    def signup_request_store_exists(self) -> bool:
        return self.signup_store

    def list_active_assignments_for_user(self, user_id: UUID) -> list[AssignmentRecord]:
        return [self._assignment(user_id)] if self.assignment_status == "ACTIVE" else []

    def get_active_assignment_for_user(self, *, user_id: UUID, assignment_id: UUID) -> AssignmentRecord | None:
        if assignment_id != self.assignment_id or self.assignment_status != "ACTIVE":
            return None
        return self._assignment(user_id)

    def list_permission_keys_for_role(self, role_id: UUID) -> list[str]:
        return self.permissions if role_id == self.role_id else []

    def get_current_subscription_entitlements(self, tenant_id: UUID | None) -> dict[str, object]:
        return self.modules

    def guardian_has_student_link(self, *, user_id: UUID, tenant_id: UUID, student_id: UUID) -> bool:
        return self.guardian_link and user_id == self.user_id and tenant_id == self.tenant_id

    def _assignment(self, user_id: UUID) -> AssignmentRecord:
        return AssignmentRecord(
            id=self.assignment_id,
            user_id=user_id,
            role_id=self.role_id,
            role_code="PARENT_GUARDIAN",
            role_label="Parent / Guardian",
            role_status="ACTIVE",
            scope_type="TENANT",
            tenant_id=self.tenant_id,
            tenant_name="Test College",
            tenant_status="ACTIVE",
            branch_id=self.branch_id,
            branch_name="Main Campus",
            branch_status="ACTIVE",
            status="ACTIVE",
            valid_from=datetime.utcnow() - timedelta(days=1),
            valid_until=None,
        )


def test_unmapped_application_user_is_denied() -> None:
    service = AuthenticationService(FakeAuthRepository())  # type: ignore[arg-type]
    with pytest.raises(ApplicationUserNotMappedError):
        service.resolve_current_user(uuid4(), None)


def test_inactive_application_user_is_denied() -> None:
    repo = FakeAuthRepository()
    repo.user_status = "BLOCKED"
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    with pytest.raises(ApplicationUserInactiveError):
        service.resolve_current_user(repo.user_id, None)


def test_valid_context_response_serialization() -> None:
    repo = FakeAuthRepository()
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    response = service.resolve_current_user(repo.user_id, repo.assignment_id)
    assert response.user.id == repo.user_id
    assert response.active_context is not None
    assert response.active_context.assignment_id == repo.assignment_id
    assert "student.view" in response.active_context.permissions


def test_assignment_belonging_to_another_user_is_denied() -> None:
    repo = FakeAuthRepository()
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    with pytest.raises(InvalidAccessContextError):
        service.resolve_current_user(repo.user_id, uuid4())


def test_revoked_assignment_is_denied() -> None:
    repo = FakeAuthRepository()
    repo.assignment_status = "REVOKED"
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    response = service.resolve_current_user(repo.user_id, None)
    assert response.available_contexts == []


def test_permission_and_module_resolution() -> None:
    repo = FakeAuthRepository()
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    context = service.resolve_request_context(
        app_user_id=repo.user_id,
        assignment_id=repo.assignment_id,
        correlation_id="test",
    )
    assert context.has_permission("student.view")
    assert not context.has_permission("fee.view")
    assert context.has_module("parent-portal")
    assert not context.has_module("fees")


def test_parent_without_guardian_link_is_denied() -> None:
    repo = FakeAuthRepository()
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    context = RequestContext(
        authenticated_auth_user_id=repo.auth_user_id,
        app_user_id=repo.user_id,
        assignment_id=repo.assignment_id,
        tenant_id=repo.tenant_id,
        branch_id=None,
        canonical_role_codes=frozenset({"PARENT_GUARDIAN"}),
        permission_keys=frozenset({"parent.child_view"}),
        enabled_modules=frozenset({"parent-portal"}),
        scope_type="TENANT",
    )
    with pytest.raises(InvalidAccessContextError):
        service.validate_guardian_student_link(context=context, student_id=uuid4())


def test_parent_with_valid_guardian_link_is_allowed() -> None:
    repo = FakeAuthRepository()
    repo.guardian_link = True
    service = AuthenticationService(repo)  # type: ignore[arg-type]
    context = RequestContext(
        authenticated_auth_user_id=repo.auth_user_id,
        app_user_id=repo.user_id,
        assignment_id=repo.assignment_id,
        tenant_id=repo.tenant_id,
        branch_id=None,
        canonical_role_codes=frozenset({"PARENT_GUARDIAN"}),
        permission_keys=frozenset({"parent.child_view"}),
        enabled_modules=frozenset({"parent-portal"}),
        scope_type="TENANT",
    )
    service.validate_guardian_student_link(context=context, student_id=uuid4())


def test_password_login_fails_closed_until_credential_store_exists() -> None:
    service = AuthenticationService(FakeAuthRepository())  # type: ignore[arg-type]
    with pytest.raises(CredentialStoreNotConfiguredError):
        service.authenticate_with_password(
            login_identifier="test@example.com",
            password="not-used",
            requested_assignment_id=None,
        )


def test_password_hash_verification_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "password_hash_iterations", 210000)
    monkeypatch.setattr(settings, "password_pepper", "test-pepper")
    salt = generate_password_salt()
    stored_hash = hash_password("CorrectHorseBatteryStaple", salt=salt)
    assert verify_password(
        "CorrectHorseBatteryStaple",
        expected_hash=stored_hash,
        salt=salt,
        iterations=settings.password_hash_iterations,
    )
    assert not verify_password(
        "wrong-password",
        expected_hash=stored_hash,
        salt=salt,
        iterations=settings.password_hash_iterations,
    )
