"""Authentication data access for application users and access contexts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, insert, inspect, or_, select
from sqlalchemy.orm import Session

from app.core.security.passwords import normalize_login_identifier
from app.modules.authentication.models import SignupRequest, UserCredential
from app.modules.branches.models import Branch
from app.modules.platform_admin.models import SubscriptionPlan, Tenant, TenantSubscription
from app.modules.students.models import Guardian, StudentGuardianLink
from app.modules.users.models import AppUser, Permission, Role, RolePermission, UserAccessAssignment


@dataclass(frozen=True)
class UserRecord:
    id: UUID
    auth_user_id: UUID | None
    tenant_id: UUID | None
    account_category: str
    full_name: str
    email: str | None
    status: str
    login_enabled: bool


@dataclass(frozen=True)
class AssignmentRecord:
    id: UUID
    user_id: UUID
    role_id: UUID
    role_code: str
    role_label: str
    role_status: str
    scope_type: str
    tenant_id: UUID | None
    tenant_name: str | None
    tenant_status: str | None
    branch_id: UUID | None
    branch_name: str | None
    branch_status: str | None
    status: str
    valid_from: datetime
    valid_until: datetime | None


@dataclass(frozen=True)
class CredentialRecord:
    user_id: UUID
    login_identifier_normalized: str
    password_hash: str
    password_salt: str
    password_algorithm: str
    password_iterations: int
    status: str
    must_change_password: bool
    locked_until: datetime | None


class AuthenticationRepository:
    """Read-only authentication repository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_user_by_auth_user_id(self, auth_user_id: UUID) -> UserRecord | None:
        table = AppUser.__table__
        row = self.session.execute(select(table).where(table.c.auth_user_id == auth_user_id)).mappings().first()
        return self._user_from_row(row) if row else None

    def get_user_by_id(self, user_id: UUID) -> UserRecord | None:
        table = AppUser.__table__
        row = self.session.execute(select(table).where(table.c.id == user_id)).mappings().first()
        return self._user_from_row(row) if row else None

    def get_user_by_login_identifier(self, identifier: str) -> UserRecord | None:
        table = AppUser.__table__
        normalized = identifier.strip().lower()
        row = self.session.execute(
            select(table).where(table.c.email.is_not(None), table.c.email.ilike(normalized))
        ).mappings().first()
        return self._user_from_row(row) if row else None

    def credential_store_exists(self) -> bool:
        bind = self.session.get_bind()
        return inspect(bind).has_table("sms_user_credentials", schema="public")

    def signup_request_store_exists(self) -> bool:
        bind = self.session.get_bind()
        return inspect(bind).has_table("sms_signup_requests", schema="public")

    def get_active_credential_by_identifier(self, identifier: str) -> CredentialRecord | None:
        table = UserCredential.__table__
        normalized = normalize_login_identifier(identifier)
        row = self.session.execute(
            select(table).where(
                table.c.login_identifier_normalized == normalized,
                table.c.status.in_(["ACTIVE", "LOCKED", "PASSWORD_RESET_REQUIRED"]),
            )
        ).mappings().first()
        if row is None:
            return None
        return CredentialRecord(
            user_id=row["user_id"],
            login_identifier_normalized=row["login_identifier_normalized"],
            password_hash=row["password_hash"],
            password_salt=row["password_salt"],
            password_algorithm=row["password_algorithm"],
            password_iterations=row["password_iterations"],
            status=row["status"],
            must_change_password=bool(row["must_change_password"]),
            locked_until=row["locked_until"],
        )

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
    ) -> UUID:
        table = SignupRequest.__table__
        row = self.session.execute(
            insert(table)
            .values(
                requested_portal=requested_portal,
                full_name=full_name.strip(),
                email=email.strip(),
                mobile=mobile.strip() if mobile else None,
                institution_name=institution_name.strip() if institution_name else None,
                branch_name=branch_name.strip() if branch_name else None,
                message=message.strip() if message else None,
            )
            .returning(table.c.id)
        ).one()
        return UUID(str(row[0]))

    def _assignment_select(self) -> Select[Any]:
        assignment = UserAccessAssignment.__table__
        role = Role.__table__
        tenant = Tenant.__table__
        branch = Branch.__table__
        return select(
            assignment.c.id,
            assignment.c.user_id,
            assignment.c.role_id,
            role.c.role_code,
            role.c.default_name.label("role_label"),
            role.c.status.label("role_status"),
            assignment.c.scope_type,
            assignment.c.tenant_id,
            tenant.c.display_name.label("tenant_name"),
            tenant.c.status.label("tenant_status"),
            assignment.c.branch_id,
            branch.c.display_name.label("branch_name"),
            branch.c.status.label("branch_status"),
            assignment.c.status,
            assignment.c.valid_from,
            assignment.c.valid_until,
        ).select_from(
            assignment.join(role, assignment.c.role_id == role.c.id)
            .outerjoin(tenant, assignment.c.tenant_id == tenant.c.id)
            .outerjoin(
                branch,
                and_(assignment.c.tenant_id == branch.c.tenant_id, assignment.c.branch_id == branch.c.id),
            )
        )

    def list_active_assignments_for_user(self, user_id: UUID) -> list[AssignmentRecord]:
        assignment = UserAccessAssignment.__table__
        now = datetime.utcnow()
        rows = self.session.execute(
            self._assignment_select().where(
                assignment.c.user_id == user_id,
                assignment.c.status == "ACTIVE",
                assignment.c.valid_from <= now,
                or_(assignment.c.valid_until.is_(None), assignment.c.valid_until > now),
            )
        ).mappings()
        return [self._assignment_from_row(row) for row in rows]

    def get_active_assignment_for_user(
        self,
        *,
        user_id: UUID,
        assignment_id: UUID,
    ) -> AssignmentRecord | None:
        assignment = UserAccessAssignment.__table__
        now = datetime.utcnow()
        row = self.session.execute(
            self._assignment_select().where(
                assignment.c.id == assignment_id,
                assignment.c.user_id == user_id,
                assignment.c.status == "ACTIVE",
                assignment.c.valid_from <= now,
                or_(assignment.c.valid_until.is_(None), assignment.c.valid_until > now),
            )
        ).mappings().first()
        return self._assignment_from_row(row) if row else None

    def list_permission_keys_for_role(self, role_id: UUID) -> list[str]:
        role_permission = RolePermission.__table__
        permission = Permission.__table__
        rows = self.session.execute(
            select(permission.c.permission_key)
            .select_from(role_permission.join(permission, role_permission.c.permission_id == permission.c.id))
            .where(
                role_permission.c.role_id == role_id,
                role_permission.c.effect == "GRANT",
                permission.c.status == "ACTIVE",
            )
            .order_by(permission.c.permission_key)
        )
        return [row[0] for row in rows]

    def get_current_subscription_entitlements(self, tenant_id: UUID | None) -> dict[str, Any]:
        if tenant_id is None:
            return {"modules": ["dashboard", "platform-admin", "audit", "reports"]}

        subscription = TenantSubscription.__table__
        plan = SubscriptionPlan.__table__
        now = datetime.utcnow()
        row = self.session.execute(
            select(
                subscription.c.entitlement_overrides,
                plan.c.entitlements.label("plan_entitlements"),
            )
            .select_from(subscription.join(plan, subscription.c.plan_id == plan.c.id))
            .where(
                subscription.c.tenant_id == tenant_id,
                subscription.c.status.in_(["TRIAL", "ACTIVE", "GRACE", "PAUSED"]),
                subscription.c.starts_at <= now,
                or_(subscription.c.ends_at.is_(None), subscription.c.ends_at > now),
            )
            .order_by(subscription.c.starts_at.desc())
            .limit(1)
        ).mappings().first()
        if row is None:
            return {"modules": []}

        plan_entitlements = row["plan_entitlements"] or {}
        overrides = row["entitlement_overrides"] or {}
        if isinstance(plan_entitlements, dict) and isinstance(overrides, dict):
            return {**plan_entitlements, **overrides}
        if isinstance(plan_entitlements, list):
            return {"modules": plan_entitlements}
        return {}

    def guardian_has_student_link(self, *, user_id: UUID, tenant_id: UUID, student_id: UUID) -> bool:
        guardian = Guardian.__table__
        link = StudentGuardianLink.__table__
        row = self.session.execute(
            select(link.c.id)
            .select_from(
                guardian.join(
                    link,
                    and_(guardian.c.tenant_id == link.c.tenant_id, guardian.c.id == link.c.guardian_id),
                )
            )
            .where(
                guardian.c.tenant_id == tenant_id,
                guardian.c.portal_user_id == user_id,
                guardian.c.status == "ACTIVE",
                link.c.student_id == student_id,
                link.c.status == "ACTIVE",
                link.c.portal_access_enabled.is_(True),
                link.c.verification_status == "VERIFIED",
                or_(link.c.effective_until.is_(None), link.c.effective_until > datetime.utcnow()),
            )
        ).first()
        return row is not None

    def _user_from_row(self, row: Any) -> UserRecord:
        return UserRecord(
            id=row["id"],
            auth_user_id=row["auth_user_id"],
            tenant_id=row["tenant_id"],
            account_category=row["account_category"],
            full_name=row["full_name"],
            email=row["email"],
            status=row["status"],
            login_enabled=bool(row["login_enabled"]),
        )

    def _assignment_from_row(self, row: Any) -> AssignmentRecord:
        return AssignmentRecord(
            id=row["id"],
            user_id=row["user_id"],
            role_id=row["role_id"],
            role_code=row["role_code"],
            role_label=row["role_label"],
            role_status=row["role_status"],
            scope_type=row["scope_type"],
            tenant_id=row["tenant_id"],
            tenant_name=row["tenant_name"],
            tenant_status=row["tenant_status"],
            branch_id=row["branch_id"],
            branch_name=row["branch_name"],
            branch_status=row["branch_status"],
            status=row["status"],
            valid_from=row["valid_from"],
            valid_until=row["valid_until"],
        )
