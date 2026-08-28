"""Audit foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, text

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class AuditEvent(Base):
    """sms_audit_events table mapping."""

    __table__ = Table(
        "sms_audit_events",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id"),
        uuid_col("branch_id"),
        uuid_col("actor_user_id", nullable=False),
        jsonb("effective_role_codes", default="'[]'::jsonb"),
        varchar("permission_key", 120),
        varchar("module_code", 60, nullable=False),
        varchar("action_key", 120, nullable=False),
        varchar("target_type", 80),
        uuid_col("target_id"),
        jsonb("old_values", nullable=True, default=None),
        jsonb("new_values", nullable=True, default=None),
        text_col("reason"),
        jsonb("context"),
        text_col("outcome", nullable=False),
        uuid_col("correlation_id", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        CheckConstraint(
            "outcome IN ('SUCCEEDED', 'REJECTED', 'DENIED', 'FAILED')",
            name="ck_sms_audit_events_outcome",
        ),
        CheckConstraint(
            "branch_id IS NULL OR tenant_id IS NOT NULL", name="ck_sms_audit_events_branch_scope"
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_audit_events_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_audit_events_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["actor_user_id"],
            ["sms_users.id"],
            name="fk_sms_audit_events_actor",
            ondelete="RESTRICT",
        ),
        Index("ix_sms_audit_events_scope_time", "tenant_id", "branch_id", text("created_at DESC")),
        Index("ix_sms_audit_events_actor_time", "actor_user_id", text("created_at DESC")),
        Index("ix_sms_audit_events_target", "target_type", "target_id"),
        Index("ix_sms_audit_events_correlation", "correlation_id"),
    )
