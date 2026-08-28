"""User and RBAC foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    Table,
    UniqueConstraint,
    text,
)

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    bool_col,
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class AppUser(Base):
    """sms_users table mapping."""

    __table__ = Table(
        "sms_users",
        Base.metadata,
        uuid_pk(),
        uuid_col("auth_user_id"),
        uuid_col("tenant_id"),
        text_col("account_category", nullable=False),
        varchar("full_name", 200, nullable=False),
        varchar("email", 320),
        varchar("mobile", 30),
        text_col("status", nullable=False, default="'INVITED'"),
        bool_col("login_enabled", default="true"),
        bool_col("is_system_account", default="false"),
        uuid_col("last_active_tenant_id"),
        uuid_col("last_active_branch_id"),
        jsonb("preferences"),
        uuid_col("created_by"),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("auth_user_id", name="uq_sms_users_auth_user_id"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_users_tenant_id_id"),
        CheckConstraint(
            "account_category IN ('PLATFORM', 'TENANT')", name="ck_sms_users_account_category"
        ),
        CheckConstraint(
            "status IN ('INVITED', 'ACTIVE', 'BLOCKED', 'LOCKED', 'INACTIVE')",
            name="ck_sms_users_status",
        ),
        CheckConstraint(
            "(account_category = 'PLATFORM' AND tenant_id IS NULL) OR (account_category = 'TENANT' AND tenant_id IS NOT NULL)",
            name="ck_sms_users_tenant_category",
        ),
        CheckConstraint(
            "NOT is_system_account OR login_enabled = false", name="ck_sms_users_system_login"
        ),
        CheckConstraint(
            "last_active_branch_id IS NULL OR last_active_tenant_id IS NOT NULL",
            name="ck_sms_users_last_active_context",
        ),
        ForeignKeyConstraint(
            ["tenant_id"], ["sms_tenants.id"], name="fk_sms_users_tenant", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["last_active_tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_users_last_active_tenant",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["sms_users.id"], name="fk_sms_users_created_by", ondelete="SET NULL"
        ),
        ForeignKeyConstraint(
            ["updated_by"], ["sms_users.id"], name="fk_sms_users_updated_by", ondelete="SET NULL"
        ),
        ForeignKeyConstraint(
            ["last_active_tenant_id", "last_active_branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_users_last_active_branch_context",
            ondelete="SET NULL",
        ),
        Index("ix_sms_users_tenant_status", "tenant_id", "status"),
        Index(
            "ix_sms_users_email_lower",
            text("lower(email)"),
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index("ix_sms_users_mobile", "mobile", postgresql_where=text("mobile IS NOT NULL")),
    )


class Role(Base):
    """sms_roles table mapping."""

    __table__ = Table(
        "sms_roles",
        Base.metadata,
        uuid_pk(),
        varchar("role_code", 80, nullable=False),
        varchar("default_name", 150, nullable=False),
        text_col("scope_type", nullable=False),
        bool_col("is_system_role", default="true"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        timestamp("created_at", nullable=False, default_now=True),
        UniqueConstraint("role_code", name="uq_sms_roles_role_code"),
        CheckConstraint(
            "role_code IN ('SAAS_SUPER_ADMIN', 'INSTITUTION_ADMIN', 'BRANCH_ADMIN', 'OFFICE_STAFF', 'PARENT_GUARDIAN')",
            name="ck_sms_roles_role_code",
        ),
        CheckConstraint(
            "scope_type IN ('PLATFORM', 'TENANT', 'BRANCH')", name="ck_sms_roles_scope_type"
        ),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_sms_roles_status"),
        Index("ix_sms_roles_scope_status", "scope_type", "status"),
    )


class Permission(Base):
    """sms_permissions table mapping."""

    __table__ = Table(
        "sms_permissions",
        Base.metadata,
        uuid_pk(),
        varchar("permission_key", 120, nullable=False),
        varchar("module_code", 60, nullable=False),
        text_col("description", nullable=False),
        jsonb("scope_expectations"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        uuid_col("created_by"),
        timestamp("created_at", nullable=False, default_now=True),
        UniqueConstraint("permission_key", name="uq_sms_permissions_permission_key"),
        CheckConstraint(
            "permission_key ~ '^[a-z0-9_]+(\\.[a-z0-9_]+)+$'", name="ck_sms_permissions_key_format"
        ),
        CheckConstraint("status IN ('ACTIVE', 'DEPRECATED')", name="ck_sms_permissions_status"),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_permissions_created_by",
            ondelete="SET NULL",
        ),
        Index("ix_sms_permissions_module_status", "module_code", "status"),
    )


class RolePermission(Base):
    """sms_role_permissions table mapping."""

    __table__ = Table(
        "sms_role_permissions",
        Base.metadata,
        uuid_col("role_id", nullable=False),
        uuid_col("permission_id", nullable=False),
        text_col("effect", nullable=False, default="'GRANT'"),
        jsonb("conditions"),
        uuid_col("created_by"),
        timestamp("created_at", nullable=False, default_now=True),
        PrimaryKeyConstraint("role_id", "permission_id", name="pk_sms_role_permissions"),
        CheckConstraint("effect = 'GRANT'", name="ck_sms_role_permissions_effect"),
        ForeignKeyConstraint(
            ["role_id"], ["sms_roles.id"], name="fk_sms_role_permissions_role", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["permission_id"],
            ["sms_permissions.id"],
            name="fk_sms_role_permissions_permission",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_role_permissions_created_by",
            ondelete="SET NULL",
        ),
        Index("ix_sms_role_permissions_permission", "permission_id"),
        Index("ix_sms_role_permissions_role", "role_id"),
    )


class UserAccessAssignment(Base):
    """sms_user_access_assignments table mapping."""

    __table__ = Table(
        "sms_user_access_assignments",
        Base.metadata,
        uuid_pk(),
        uuid_col("user_id", nullable=False),
        uuid_col("role_id", nullable=False),
        text_col("scope_type", nullable=False),
        uuid_col("tenant_id"),
        uuid_col("branch_id"),
        text_col("status", nullable=False, default="'PENDING'"),
        timestamp("valid_from", nullable=False, default_now=True),
        timestamp("valid_until"),
        bool_col("is_primary", default="false"),
        jsonb("permission_overrides"),
        uuid_col("assigned_by", nullable=False),
        uuid_col("revoked_by"),
        text_col("revocation_reason"),
        jsonb("metadata"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "scope_type IN ('PLATFORM', 'TENANT', 'BRANCH')",
            name="ck_sms_user_access_assignments_scope_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'SUSPENDED', 'EXPIRED', 'REVOKED')",
            name="ck_sms_user_access_assignments_status",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="ck_sms_user_access_assignments_validity",
        ),
        CheckConstraint(
            "status <> 'REVOKED' OR (revoked_by IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="ck_sms_user_access_assignments_revocation",
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["sms_users.id"],
            name="fk_sms_user_access_assignments_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["role_id"],
            ["sms_roles.id"],
            name="fk_sms_user_access_assignments_role",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_user_access_assignments_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_user_access_assignments_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assigned_by"],
            ["sms_users.id"],
            name="fk_sms_user_access_assignments_assigned_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["revoked_by"],
            ["sms_users.id"],
            name="fk_sms_user_access_assignments_revoked_by",
            ondelete="SET NULL",
        ),
        Index(
            "uq_sms_user_access_assignments_platform_active",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text(
                "scope_type = 'PLATFORM' AND status IN ('PENDING', 'ACTIVE', 'SUSPENDED')"
            ),
        ),
        Index(
            "uq_sms_user_access_assignments_tenant_active",
            "user_id",
            "tenant_id",
            "role_id",
            unique=True,
            postgresql_where=text(
                "scope_type = 'TENANT' AND status IN ('PENDING', 'ACTIVE', 'SUSPENDED')"
            ),
        ),
        Index(
            "uq_sms_user_access_assignments_branch_active",
            "user_id",
            "tenant_id",
            "branch_id",
            "role_id",
            unique=True,
            postgresql_where=text(
                "scope_type = 'BRANCH' AND status IN ('PENDING', 'ACTIVE', 'SUSPENDED')"
            ),
        ),
        Index(
            "ix_sms_user_access_assignments_user_status_validity",
            "user_id",
            "status",
            "valid_from",
            "valid_until",
        ),
        Index(
            "ix_sms_user_access_assignments_scope_lookup",
            "tenant_id",
            "branch_id",
            "role_id",
            "status",
        ),
    )
