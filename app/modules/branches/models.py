"""Branch foundation SQLAlchemy models."""

# mypy: ignore-errors

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class Branch(Base):
    """sms_branches table mapping."""

    id: Any
    tenant_id: Any
    branch_code: Any
    display_name: Any
    status: Any

    __table__ = Table(
        "sms_branches",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        varchar("branch_code", 30, nullable=False),
        varchar("legal_name", 250),
        varchar("display_name", 200, nullable=False),
        text_col("status", nullable=False, default="'DRAFT'"),
        jsonb("address_data"),
        jsonb("contact_data"),
        varchar("timezone", 50, nullable=False, default="'Asia/Kolkata'"),
        uuid_col("requested_by"),
        timestamp("requested_at"),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        uuid_col("rejected_by"),
        timestamp("rejected_at"),
        text_col("rejection_reason"),
        timestamp("activated_at"),
        timestamp("closed_at"),
        jsonb("metadata"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "branch_code", name="uq_sms_branches_tenant_code"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_branches_tenant_id_id"),
        CheckConstraint("status IN ('DRAFT', 'REQUESTED', 'APPROVED', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'INACTIVE', 'CLOSED')", name="ck_sms_branches_status"),
        CheckConstraint("status <> 'REJECTED' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL)", name="ck_sms_branches_rejection_fields"),
        CheckConstraint("status NOT IN ('APPROVED', 'ACTIVE') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)", name="ck_sms_branches_approval_fields"),
        CheckConstraint("status <> 'ACTIVE' OR activated_at IS NOT NULL", name="ck_sms_branches_active_timestamp"),
        CheckConstraint("status <> 'CLOSED' OR closed_at IS NOT NULL", name="ck_sms_branches_closed_timestamp"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_branches_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["requested_by"], ["sms_users.id"], name="fk_sms_branches_requested_by", ondelete="SET NULL"),
        ForeignKeyConstraint(["approved_by"], ["sms_users.id"], name="fk_sms_branches_approved_by", ondelete="SET NULL"),
        ForeignKeyConstraint(["rejected_by"], ["sms_users.id"], name="fk_sms_branches_rejected_by", ondelete="SET NULL"),
        Index("ix_sms_branches_tenant_status", "tenant_id", "status"),
        Index("ix_sms_branches_tenant_code", "tenant_id", "branch_code"),
    )
