"""Workflow foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class WorkflowRequest(Base):
    """sms_workflow_requests table mapping."""

    __table__ = Table(
        "sms_workflow_requests",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id"),
        varchar("module_code", 60, nullable=False),
        varchar("request_type", 100, nullable=False),
        varchar("target_type", 80, nullable=False),
        uuid_col("target_id"),
        text_col("status", nullable=False, default="'DRAFT'"),
        uuid_col("maker_user_id", nullable=False),
        timestamp("submitted_at"),
        uuid_col("approver_user_id"),
        timestamp("decision_at"),
        text_col("reason"),
        jsonb("before_data", nullable=True, default=None),
        jsonb("requested_changes"),
        jsonb("decision_data"),
        jsonb("policy_snapshot"),
        uuid_col("correlation_id", nullable=False, default="gen_random_uuid()"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'APPLIED', 'CANCELLED')",
            name="ck_sms_workflow_requests_status",
        ),
        CheckConstraint(
            "approver_user_id IS NULL OR approver_user_id <> maker_user_id",
            name="ck_sms_workflow_requests_maker_approver",
        ),
        CheckConstraint(
            "status NOT IN ('APPROVED', 'REJECTED', 'APPLIED') OR (approver_user_id IS NOT NULL AND decision_at IS NOT NULL)",
            name="ck_sms_workflow_requests_decision_fields",
        ),
        CheckConstraint(
            "status <> 'REJECTED' OR reason IS NOT NULL",
            name="ck_sms_workflow_requests_rejection_reason",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_workflow_requests_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_workflow_requests_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["maker_user_id"],
            ["sms_users.id"],
            name="fk_sms_workflow_requests_maker",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approver_user_id"],
            ["sms_users.id"],
            name="fk_sms_workflow_requests_approver",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_workflow_requests_queue",
            "tenant_id",
            "branch_id",
            "module_code",
            "request_type",
            "status",
        ),
        Index("ix_sms_workflow_requests_target", "target_type", "target_id"),
        Index("ix_sms_workflow_requests_correlation", "correlation_id"),
    )
