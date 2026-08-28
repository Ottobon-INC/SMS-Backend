"""Platform administration foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint, text

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    bool_col,
    int_col,
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class Tenant(Base):
    """sms_tenants table mapping."""

    __table__ = Table(
        "sms_tenants",
        Base.metadata,
        uuid_pk(),
        varchar("tenant_code", 30, nullable=False),
        varchar("legal_name", 250, nullable=False),
        varchar("display_name", 200, nullable=False),
        text_col("status", nullable=False, default="'DRAFT'"),
        varchar("primary_domain", 255),
        varchar("default_language", 10, nullable=False, default="'en'"),
        varchar("timezone", 50, nullable=False, default="'Asia/Kolkata'"),
        jsonb("contact_data"),
        jsonb("address_data"),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        uuid_col("suspended_by"),
        timestamp("suspended_at"),
        text_col("suspension_reason"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_code", name="uq_sms_tenants_tenant_code"),
        CheckConstraint(
            "status IN ('DRAFT', 'PENDING_APPROVAL', 'ACTIVE', 'SUSPENDED', 'READ_ONLY', 'CLOSED')",
            name="ck_sms_tenants_status",
        ),
        CheckConstraint(
            "status <> 'SUSPENDED' OR (suspended_by IS NOT NULL AND suspended_at IS NOT NULL AND suspension_reason IS NOT NULL)",
            name="ck_sms_tenants_suspension_fields",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_tenants_approved_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["suspended_by"],
            ["sms_users.id"],
            name="fk_sms_tenants_suspended_by",
            ondelete="SET NULL",
        ),
        Index("ix_sms_tenants_status", "status"),
        Index(
            "ix_sms_tenants_primary_domain",
            text("lower(primary_domain)"),
            postgresql_where=text("primary_domain IS NOT NULL"),
        ),
    )


class SubscriptionPlan(Base):
    """sms_subscription_plans table mapping."""

    __table__ = Table(
        "sms_subscription_plans",
        Base.metadata,
        uuid_pk(),
        varchar("plan_code", 50, nullable=False),
        int_col("version_no", nullable=False),
        varchar("plan_name", 150, nullable=False),
        text_col("description"),
        jsonb("entitlements"),
        jsonb("limits"),
        jsonb("branding_permissions"),
        text_col("status", nullable=False, default="'DRAFT'"),
        timestamp("effective_from"),
        timestamp("effective_until"),
        uuid_col("created_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("plan_code", "version_no", name="uq_sms_subscription_plans_code_version"),
        CheckConstraint("version_no > 0", name="ck_sms_subscription_plans_version"),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="ck_sms_subscription_plans_status"
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from",
            name="ck_sms_subscription_plans_effective_dates",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_subscription_plans_created_by",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_subscription_plans_lookup",
            "plan_code",
            "status",
            "effective_from",
            "effective_until",
        ),
        Index(
            "uq_sms_subscription_plans_current_active",
            "plan_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE' AND effective_until IS NULL"),
        ),
    )


class TenantSubscription(Base):
    """sms_tenant_subscriptions table mapping."""

    __table__ = Table(
        "sms_tenant_subscriptions",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("plan_id", nullable=False),
        text_col("status", nullable=False),
        text_col("billing_cycle"),
        timestamp("starts_at", nullable=False),
        timestamp("ends_at"),
        timestamp("trial_ends_at"),
        bool_col("auto_renew", default="false"),
        jsonb("entitlement_overrides"),
        jsonb("limit_overrides"),
        jsonb("usage_cache", nullable=True, default=None),
        timestamp("usage_cache_as_of"),
        jsonb("pause_policy"),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "status IN ('TRIAL', 'ACTIVE', 'PAUSED', 'GRACE', 'EXPIRED', 'CANCELLED')",
            name="ck_sms_tenant_subscriptions_status",
        ),
        CheckConstraint(
            "billing_cycle IS NULL OR billing_cycle IN ('MONTHLY', 'QUARTERLY', 'ANNUAL', 'CUSTOM')",
            name="ck_sms_tenant_subscriptions_billing_cycle",
        ),
        CheckConstraint(
            "ends_at IS NULL OR ends_at > starts_at", name="ck_sms_tenant_subscriptions_dates"
        ),
        CheckConstraint(
            "trial_ends_at IS NULL OR trial_ends_at >= starts_at",
            name="ck_sms_tenant_subscriptions_trial_date",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_tenant_subscriptions_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["plan_id"],
            ["sms_subscription_plans.id"],
            name="fk_sms_tenant_subscriptions_plan",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_tenant_subscriptions_approved_by",
            ondelete="SET NULL",
        ),
        Index(
            "uq_sms_tenant_subscriptions_current",
            "tenant_id",
            unique=True,
            postgresql_where=text("status IN ('TRIAL', 'ACTIVE', 'PAUSED', 'GRACE')"),
        ),
        Index("ix_sms_tenant_subscriptions_tenant_status", "tenant_id", "status"),
        Index("ix_sms_tenant_subscriptions_plan_status", "plan_id", "status"),
    )


class Configuration(Base):
    """sms_configurations table mapping."""

    __table__ = Table(
        "sms_configurations",
        Base.metadata,
        uuid_pk(),
        text_col("scope_type", nullable=False),
        uuid_col("tenant_id"),
        uuid_col("branch_id"),
        varchar("role_code", 80),
        varchar("setting_key", 120, nullable=False),
        int_col("version_no", nullable=False),
        jsonb("value", default=None),
        text_col("status", nullable=False, default="'DRAFT'"),
        timestamp("effective_from"),
        timestamp("effective_until"),
        uuid_col("supersedes_id"),
        uuid_col("created_by", nullable=False),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "scope_type IN ('PLATFORM', 'TENANT', 'BRANCH', 'ROLE')",
            name="ck_sms_configurations_scope_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'RETIRED')", name="ck_sms_configurations_status"
        ),
        CheckConstraint("version_no > 0", name="ck_sms_configurations_version"),
        CheckConstraint(
            "supersedes_id IS NULL OR supersedes_id <> id",
            name="ck_sms_configurations_supersedes_self",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_configurations_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_configurations_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["role_code"],
            ["sms_roles.role_code"],
            name="fk_sms_configurations_role_code",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_id"],
            ["sms_configurations.id"],
            name="fk_sms_configurations_supersedes",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_configurations_created_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_configurations_approved_by",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_configurations_scope_lookup",
            "scope_type",
            "tenant_id",
            "branch_id",
            "role_code",
            "setting_key",
            "status",
        ),
    )


class PrivilegedAccessGrant(Base):
    """sms_privileged_access_grants table mapping."""

    __table__ = Table(
        "sms_privileged_access_grants",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id"),
        uuid_col("requested_by", nullable=False),
        timestamp("requested_at", nullable=False, default_now=True),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        timestamp("rejected_at"),
        text_col("purpose", nullable=False),
        jsonb("access_scope"),
        text_col("status", nullable=False, default="'REQUESTED'"),
        timestamp("valid_from"),
        timestamp("valid_until", nullable=False),
        uuid_col("revoked_by"),
        timestamp("revoked_at"),
        text_col("revocation_reason"),
        varchar("session_reference", 180),
        jsonb("metadata"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "status IN ('REQUESTED', 'APPROVED', 'REJECTED', 'ACTIVE', 'EXPIRED', 'REVOKED')",
            name="ck_sms_privileged_access_grants_status",
        ),
        CheckConstraint(
            "valid_until > requested_at AND (valid_from IS NULL OR valid_until > valid_from)",
            name="ck_sms_privileged_access_grants_validity",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_privileged_access_grants_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_privileged_access_grants_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requested_by"],
            ["sms_users.id"],
            name="fk_sms_privileged_access_grants_requested_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_privileged_access_grants_approved_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["revoked_by"],
            ["sms_users.id"],
            name="fk_sms_privileged_access_grants_revoked_by",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_privileged_access_grants_tenant_status_expiry",
            "tenant_id",
            "status",
            "valid_until",
        ),
        Index("ix_sms_privileged_access_grants_requester_status", "requested_by", "status"),
    )
