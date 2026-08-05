"""Authentication service for current user and access-context resolution."""

from __future__ import annotations

from uuid import UUID

from app.core.config.settings import settings
from app.core.security.context import RequestContext
from app.core.security.jwt import create_application_access_token
from app.core.security.passwords import PASSWORD_ALGORITHM, verify_password
from app.modules.authentication.exceptions import (
    ApplicationUserInactiveError,
    ApplicationUserNotMappedError,
    CredentialStoreNotConfiguredError,
    InvalidAccessContextError,
    InvalidLoginCredentialsError,
    SignupRequestStoreNotConfiguredError,
)
from app.modules.authentication.repository import (
    AssignmentRecord,
    AuthenticationRepository,
    UserRecord,
)
from app.modules.authentication.schemas import (
    AccessContextSummary,
    ActiveContextResponse,
    AuthenticatedUserResponse,
    BranchSummary,
    CurrentUserResponse,
    LoginResponse,
    RoleSummary,
    SignupRequestResponse,
    TenantSummary,
)

DEFAULT_TENANT_MODULES = [
    "dashboard",
    "institution",
    "branches",
    "users",
    "academic-structure",
    "students",
    "imports",
    "fees",
    "attendance",
    "examinations",
    "notifications",
    "reports",
    "audit",
    "support",
    "parent-portal",
]
PLATFORM_MODULES = ["dashboard", "platform-admin", "audit", "reports"]


class AuthenticationService:
    """Resolve mapped application users, contexts, permissions and modules."""

    def __init__(self, repository: AuthenticationRepository) -> None:
        self.repository = repository

    def resolve_current_user(
        self,
        app_user_id: UUID,
        requested_assignment_id: UUID | None,
    ) -> CurrentUserResponse:
        user = self._require_active_user_by_id(app_user_id)
        assignments = self.repository.list_active_assignments_for_user(user.id)
        usable_assignments = [
            assignment for assignment in assignments if self._assignment_is_usable(assignment)
        ]
        contexts = [self._context_summary(assignment) for assignment in usable_assignments]
        active_context = None
        if requested_assignment_id is not None:
            active_context = self._active_context(self._require_assignment(user.id, requested_assignment_id))
        elif len(usable_assignments) == 1:
            active_context = self._active_context(usable_assignments[0])
        return CurrentUserResponse(
            user=AuthenticatedUserResponse(
                id=user.id,
                display_name=user.full_name,
                email=user.email,
                status=user.status,
                account_category=user.account_category,
            ),
            available_contexts=contexts,
            active_context=active_context,
        )

    def resolve_request_context(
        self,
        *,
        app_user_id: UUID,
        assignment_id: UUID,
        correlation_id: str | None,
    ) -> RequestContext:
        user = self._require_active_user_by_id(app_user_id)
        assignment = self._require_assignment(user.id, assignment_id)
        active_context = self._active_context(assignment)
        return RequestContext(
            authenticated_auth_user_id=user.auth_user_id or user.id,
            app_user_id=user.id,
            assignment_id=assignment.id,
            tenant_id=assignment.tenant_id,
            branch_id=assignment.branch_id,
            canonical_role_codes=frozenset(active_context.role_codes),
            permission_keys=frozenset(active_context.permissions),
            enabled_modules=frozenset(active_context.enabled_modules),
            scope_type=assignment.scope_type,
            correlation_id=correlation_id,
        )

    def authenticate_with_password(
        self,
        *,
        login_identifier: str,
        password: str,
        requested_assignment_id: UUID | None,
    ) -> LoginResponse:
        """Authenticate with local credentials.

        The current locked foundation schema has users and access assignments.
        Password verification uses the optional authentication extension table
        only after it has been created through reviewed SQL.
        """

        if not self.repository.credential_store_exists():
            raise CredentialStoreNotConfiguredError(
                "Password credential storage is not configured for this database foundation."
            )
        credential = self.repository.get_active_credential_by_identifier(login_identifier)
        if credential is None:
            raise InvalidLoginCredentialsError("Invalid username/email or password.")
        if credential.password_algorithm != PASSWORD_ALGORITHM:
            raise InvalidLoginCredentialsError("Invalid username/email or password.")
        if credential.status != "ACTIVE":
            raise InvalidLoginCredentialsError("This account cannot sign in right now.")
        if not verify_password(
            password,
            expected_hash=credential.password_hash,
            salt=credential.password_salt,
            iterations=credential.password_iterations,
        ):
            raise InvalidLoginCredentialsError("Invalid username/email or password.")
        user = self._require_active_user_by_id(credential.user_id)
        return self.build_login_response(user, requested_assignment_id)

    def create_signup_request(
        self,
        *,
        requested_portal: str,
        full_name: str,
        email: str,
        mobile: str | None,
        institution_name: str | None,
        branch_name: str | None,
        message: str | None,
    ) -> SignupRequestResponse:
        if not self.repository.signup_request_store_exists():
            raise SignupRequestStoreNotConfiguredError(
                "Signup request storage is not configured for this database foundation."
            )
        request_id = self.repository.create_signup_request(
            requested_portal=requested_portal,
            full_name=full_name,
            email=email,
            mobile=mobile,
            institution_name=institution_name,
            branch_name=branch_name,
            message=message,
        )
        return SignupRequestResponse(request_id=request_id)

    def build_login_response(self, user: UserRecord, requested_assignment_id: UUID | None) -> LoginResponse:
        current_user = self.resolve_current_user(user.id, requested_assignment_id)
        access_token = create_application_access_token(user.id)
        return LoginResponse(
            **current_user.model_dump(),
            access_token=access_token,
            expires_in_seconds=settings.access_token_expire_minutes * 60,
        )

    def validate_guardian_student_link(self, *, context: RequestContext, student_id: UUID) -> None:
        if "PARENT_GUARDIAN" not in context.canonical_role_codes or context.tenant_id is None:
            raise InvalidAccessContextError("Guardian access context required.")
        if not self.repository.guardian_has_student_link(
            user_id=context.app_user_id,
            tenant_id=context.tenant_id,
            student_id=student_id,
        ):
            raise InvalidAccessContextError("Guardian link not found.")

    def _require_active_user(self, auth_user_id: UUID) -> UserRecord:
        user = self.repository.get_user_by_auth_user_id(auth_user_id)
        if user is None:
            raise ApplicationUserNotMappedError("Application access is not configured for this account.")
        if user.status != "ACTIVE" or not user.login_enabled:
            raise ApplicationUserInactiveError("Application user is inactive or blocked.")
        return user

    def _require_active_user_by_id(self, app_user_id: UUID) -> UserRecord:
        user = self.repository.get_user_by_id(app_user_id)
        if user is None:
            raise ApplicationUserNotMappedError("Application access is not configured for this account.")
        if user.status != "ACTIVE" or not user.login_enabled:
            raise ApplicationUserInactiveError("Application user is inactive or blocked.")
        return user

    def _require_assignment(self, user_id: UUID, assignment_id: UUID) -> AssignmentRecord:
        assignment = self.repository.get_active_assignment_for_user(user_id=user_id, assignment_id=assignment_id)
        if assignment is None or not self._assignment_is_usable(assignment):
            raise InvalidAccessContextError("Invalid access context.")
        return assignment

    def _assignment_is_usable(self, assignment: AssignmentRecord) -> bool:
        if assignment.role_status != "ACTIVE":
            return False
        if assignment.scope_type == "PLATFORM":
            return True
        if assignment.scope_type == "TENANT":
            return assignment.tenant_status in {"ACTIVE", "READ_ONLY"}
        if assignment.scope_type == "BRANCH":
            return assignment.tenant_status in {"ACTIVE", "READ_ONLY"} and assignment.branch_status == "ACTIVE"
        return False

    def _context_summary(self, assignment: AssignmentRecord) -> AccessContextSummary:
        active = self._active_context(assignment)
        tenant = None
        if assignment.tenant_id is not None:
            tenant = TenantSummary(
                id=assignment.tenant_id,
                name=assignment.tenant_name or "Institution",
                status=assignment.tenant_status or "UNKNOWN",
            )
        branch = None
        if assignment.branch_id is not None:
            branch = BranchSummary(
                id=assignment.branch_id,
                name=assignment.branch_name or "Branch",
                status=assignment.branch_status or "UNKNOWN",
            )
        return AccessContextSummary(
            assignment_id=assignment.id,
            tenant=tenant,
            branch=branch,
            role=RoleSummary(code=assignment.role_code, label=assignment.role_label),
            scope_type=assignment.scope_type,
            enabled_modules=active.enabled_modules,
            permissions=active.permissions,
        )

    def _active_context(self, assignment: AssignmentRecord) -> ActiveContextResponse:
        permissions = self.repository.list_permission_keys_for_role(assignment.role_id)
        enabled_modules = self._resolve_enabled_modules(assignment)
        if assignment.role_code == "PARENT_GUARDIAN":
            enabled_modules = [module for module in enabled_modules if module == "parent-portal"]
        return ActiveContextResponse(
            assignment_id=assignment.id,
            tenant_id=assignment.tenant_id,
            branch_id=assignment.branch_id,
            role_codes=[assignment.role_code],
            permissions=permissions,
            enabled_modules=enabled_modules,
            scope_type=assignment.scope_type,
        )

    def _resolve_enabled_modules(self, assignment: AssignmentRecord) -> list[str]:
        if assignment.scope_type == "PLATFORM":
            return PLATFORM_MODULES
        entitlements = self.repository.get_current_subscription_entitlements(assignment.tenant_id)
        modules = entitlements.get("modules") or entitlements.get("enabled_modules")
        if modules == "*":
            return DEFAULT_TENANT_MODULES
        if isinstance(modules, list):
            return sorted(str(module) for module in modules)
        return []
