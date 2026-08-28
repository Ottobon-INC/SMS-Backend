"""Fee module SQLAlchemy models.

These mappings mirror the manually applied PostgreSQL fee MVP tables. The
database remains source-of-truth; these models must not be used to create or
alter tables automatically.
"""

# mypy: ignore-errors

from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    int_col,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class FeeAccount(Base):
    """sms_fee_accounts table mapping."""

    id: Any
    tenant_id: Any
    branch_id: Any
    student_id: Any
    enrollment_id: Any
    academic_year_id: Any
    assigned_fee_amount: Any
    scholarship_amount: Any
    concession_amount: Any
    net_payable_amount: Any
    total_paid_amount: Any
    outstanding_amount: Any
    payment_schedule_type: Any
    payment_schedule: Any
    status: Any

    __table__ = Table(
        "sms_fee_accounts",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("enrollment_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        varchar("currency", 3, nullable=False, default="'INR'"),
        Column("assigned_fee_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("scholarship_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("concession_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("net_payable_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("total_paid_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("total_adjusted_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("total_reversed_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        Column("outstanding_amount", Numeric(12, 2), nullable=False, server_default=text("0")),
        text_col("payment_schedule_type", nullable=False, default="'ONE_TIME'"),
        Column("payment_schedule", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
        text_col("status", nullable=False, default="'ACTIVE'"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        UniqueConstraint(
            "tenant_id", "enrollment_id", name="uq_sms_fee_accounts_tenant_enrollment"
        ),
        CheckConstraint("currency = 'INR'", name="ck_sms_fee_accounts_currency"),
        CheckConstraint(
            "assigned_fee_amount >= 0 AND scholarship_amount >= 0 AND concession_amount >= 0 "
            "AND net_payable_amount >= 0 AND total_paid_amount >= 0 AND total_adjusted_amount >= 0 "
            "AND total_reversed_amount >= 0 AND outstanding_amount >= 0",
            name="ck_sms_fee_accounts_amounts_non_negative",
        ),
        CheckConstraint(
            "payment_schedule_type IN ('ONE_TIME', 'TERM_WISE', 'INSTALLMENT_WISE', 'CUSTOM')",
            name="ck_sms_fee_accounts_schedule_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'PAID', 'PARTIALLY_PAID', 'OVERDUE', 'CLOSED', 'CANCELLED')",
            name="ck_sms_fee_accounts_status",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_fee_accounts_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_fee_accounts_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "student_id"],
            ["sms_students.tenant_id", "sms_students.id"],
            name="fk_sms_fee_accounts_student_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "enrollment_id"],
            ["sms_enrollments.tenant_id", "sms_enrollments.id"],
            name="fk_sms_fee_accounts_enrollment_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "academic_year_id"],
            ["sms_academic_years.tenant_id", "sms_academic_years.id"],
            name="fk_sms_fee_accounts_academic_year_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_fee_accounts_created_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["updated_by"],
            ["sms_users.id"],
            name="fk_sms_fee_accounts_updated_by",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_fee_accounts_scope_status",
            "tenant_id",
            "branch_id",
            "academic_year_id",
            "status",
        ),
        Index("ix_sms_fee_accounts_student", "tenant_id", "student_id"),
        Index(
            "ix_sms_fee_accounts_outstanding",
            "tenant_id",
            "branch_id",
            "outstanding_amount",
            postgresql_where=text("outstanding_amount > 0"),
        ),
    )


class FeeLedgerEntry(Base):
    """sms_fee_ledger_entries table mapping."""

    id: Any
    tenant_id: Any
    branch_id: Any
    fee_account_id: Any
    student_id: Any
    enrollment_id: Any
    academic_year_id: Any
    entry_type: Any
    balance_effect: Any
    amount: Any
    receipt_number: Any
    status: Any

    __table__ = Table(
        "sms_fee_ledger_entries",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("fee_account_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("enrollment_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        text_col("entry_type", nullable=False),
        text_col("balance_effect", nullable=False),
        Column("amount", Numeric(12, 2), nullable=False),
        text_col("payment_mode"),
        varchar("external_reference", 180),
        varchar("receipt_number", 80),
        Column("receipt_date", Date),
        varchar("payment_period_label", 80),
        Column("payment_period_due_date", Date),
        int_col("installment_number"),
        Column("entry_date", Date, nullable=False, server_default=text("CURRENT_DATE")),
        uuid_col("reversal_of_entry_id"),
        text_col("status", nullable=False, default="'POSTED'"),
        text_col("notes"),
        uuid_col("collected_by"),
        uuid_col("posted_by", nullable=False),
        timestamp("posted_at", nullable=False, default_now=True),
        uuid_col("created_by", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        CheckConstraint(
            "entry_type IN ('FEE_ASSIGNED', 'PAYMENT', 'GOVERNMENT_SCHOLARSHIP', 'CONCESSION', "
            "'ADJUSTMENT', 'REVERSAL', 'REFUND', 'LATE_FEE')",
            name="ck_sms_fee_ledger_entries_type",
        ),
        CheckConstraint(
            "balance_effect IN ('INCREASE', 'DECREASE', 'NEUTRAL')",
            name="ck_sms_fee_ledger_entries_balance_effect",
        ),
        CheckConstraint("amount > 0", name="ck_sms_fee_ledger_entries_amount_positive"),
        CheckConstraint(
            "status IN ('DRAFT', 'POSTED', 'REVERSED', 'CANCELLED')",
            name="ck_sms_fee_ledger_entries_status",
        ),
        CheckConstraint(
            "payment_mode IS NULL OR payment_mode IN ('CASH', 'UPI', 'BANK_TRANSFER', 'CHEQUE', 'CARD', 'OTHER')",
            name="ck_sms_fee_ledger_entries_payment_mode",
        ),
        CheckConstraint(
            "entry_type <> 'PAYMENT' OR (payment_mode IS NOT NULL AND receipt_number IS NOT NULL AND receipt_date IS NOT NULL)",
            name="ck_sms_fee_ledger_entries_payment_fields",
        ),
        CheckConstraint(
            "entry_type <> 'REVERSAL' OR reversal_of_entry_id IS NOT NULL",
            name="ck_sms_fee_ledger_entries_reversal_fields",
        ),
        CheckConstraint(
            "installment_number IS NULL OR installment_number > 0",
            name="ck_sms_fee_ledger_entries_installment_number",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_fee_ledger_entries_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_fee_ledger_entries_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fee_account_id"],
            ["sms_fee_accounts.id"],
            name="fk_sms_fee_ledger_entries_fee_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "student_id"],
            ["sms_students.tenant_id", "sms_students.id"],
            name="fk_sms_fee_ledger_entries_student_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "enrollment_id"],
            ["sms_enrollments.tenant_id", "sms_enrollments.id"],
            name="fk_sms_fee_ledger_entries_enrollment_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "academic_year_id"],
            ["sms_academic_years.tenant_id", "sms_academic_years.id"],
            name="fk_sms_fee_ledger_entries_academic_year_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reversal_of_entry_id"],
            ["sms_fee_ledger_entries.id"],
            name="fk_sms_fee_ledger_entries_reversal_of",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["collected_by"],
            ["sms_users.id"],
            name="fk_sms_fee_ledger_entries_collected_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["posted_by"],
            ["sms_users.id"],
            name="fk_sms_fee_ledger_entries_posted_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_fee_ledger_entries_created_by",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_sms_fee_ledger_entries_receipt",
            "tenant_id",
            "branch_id",
            "receipt_number",
            unique=True,
            postgresql_where=text("receipt_number IS NOT NULL"),
        ),
        Index(
            "ix_sms_fee_ledger_entries_account_date", "fee_account_id", "entry_date", "created_at"
        ),
        Index(
            "ix_sms_fee_ledger_entries_scope_type",
            "tenant_id",
            "branch_id",
            "academic_year_id",
            "entry_type",
        ),
        Index(
            "ix_sms_fee_ledger_entries_external_reference",
            "tenant_id",
            "branch_id",
            "external_reference",
            postgresql_where=text("external_reference IS NOT NULL"),
        ),
    )


class FeeAdjustmentRequest(Base):
    """sms_fee_adjustment_requests table mapping."""

    id: Any
    tenant_id: Any
    branch_id: Any
    fee_account_id: Any
    student_id: Any
    enrollment_id: Any
    academic_year_id: Any
    adjustment_type: Any
    requested_amount: Any
    status: Any

    __table__ = Table(
        "sms_fee_adjustment_requests",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("fee_account_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("enrollment_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        text_col("adjustment_type", nullable=False),
        Column("requested_amount", Numeric(12, 2), nullable=False),
        text_col("reason", nullable=False),
        text_col("decision_notes"),
        text_col("status", nullable=False, default="'SUBMITTED'"),
        uuid_col("requested_by", nullable=False),
        timestamp("requested_at", nullable=False, default_now=True),
        uuid_col("approved_by"),
        timestamp("approved_at"),
        uuid_col("rejected_by"),
        timestamp("rejected_at"),
        uuid_col("posted_ledger_entry_id"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
        CheckConstraint(
            "adjustment_type IN ('GOVERNMENT_SCHOLARSHIP', 'MANAGEMENT_CONCESSION', "
            "'RETENTION_DISCOUNT', 'LATE_FEE_WAIVER', 'CORRECTION', 'OTHER')",
            name="ck_sms_fee_adjustment_requests_type",
        ),
        CheckConstraint("requested_amount > 0", name="ck_sms_fee_adjustment_requests_amount"),
        CheckConstraint(
            "status IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'POSTED', 'CANCELLED')",
            name="ck_sms_fee_adjustment_requests_status",
        ),
        CheckConstraint(
            "status NOT IN ('APPROVED', 'POSTED') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_sms_fee_adjustment_requests_approved_fields",
        ),
        CheckConstraint(
            "status <> 'REJECTED' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL AND decision_notes IS NOT NULL)",
            name="ck_sms_fee_adjustment_requests_rejected_fields",
        ),
        CheckConstraint(
            "status <> 'POSTED' OR posted_ledger_entry_id IS NOT NULL",
            name="ck_sms_fee_adjustment_requests_posted_fields",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_fee_adjustment_requests_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_fee_adjustment_requests_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["fee_account_id"],
            ["sms_fee_accounts.id"],
            name="fk_sms_fee_adjustment_requests_fee_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "student_id"],
            ["sms_students.tenant_id", "sms_students.id"],
            name="fk_sms_fee_adjustment_requests_student_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "enrollment_id"],
            ["sms_enrollments.tenant_id", "sms_enrollments.id"],
            name="fk_sms_fee_adjustment_requests_enrollment_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "academic_year_id"],
            ["sms_academic_years.tenant_id", "sms_academic_years.id"],
            name="fk_sms_fee_adjustment_requests_academic_year_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["requested_by"],
            ["sms_users.id"],
            name="fk_sms_fee_adjustment_requests_requested_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_fee_adjustment_requests_approved_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["rejected_by"],
            ["sms_users.id"],
            name="fk_sms_fee_adjustment_requests_rejected_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["posted_ledger_entry_id"],
            ["sms_fee_ledger_entries.id"],
            name="fk_sms_fee_adjustment_requests_posted_ledger_entry",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_fee_adjustment_requests_scope_status",
            "tenant_id",
            "branch_id",
            "academic_year_id",
            "status",
        ),
        Index("ix_sms_fee_adjustment_requests_account", "fee_account_id", "status"),
        Index("ix_sms_fee_adjustment_requests_requested_by", "requested_by", "requested_at"),
    )
