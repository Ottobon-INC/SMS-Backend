"""Import foundation SQLAlchemy models."""

# mypy: ignore-errors

from typing import Any

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


class ImportBatch(Base):
    """sms_import_batches table mapping."""

    __allow_unmapped__ = True

    id: Any
    tenant_id: Any
    branch_id: Any
    module_code: Any
    idempotency_key: Any
    status: Any
    summary: Any
    committed_at: Any

    __table__ = Table(
        "sms_import_batches",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id"),
        varchar("module_code", 50, nullable=False),
        varchar("import_type", 80, nullable=False),
        varchar("schema_version", 30, nullable=False),
        text_col("source_filename", nullable=False),
        text_col("storage_key", nullable=False),
        varchar("checksum", 128, nullable=False),
        varchar("idempotency_key", 180, nullable=False),
        bool_col("is_high_risk", default="false"),
        text_col("status", nullable=False, default="'UPLOADED'"),
        jsonb("summary"),
        uuid_col("created_by", nullable=False),
        uuid_col("submitted_by"),
        uuid_col("approved_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("submitted_at"),
        timestamp("approved_at"),
        timestamp("committed_at"),
        jsonb("metadata"),
        UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_sms_import_batches_tenant_idempotency"
        ),
        CheckConstraint(
            "status IN ('UPLOADED', 'VALIDATING', 'PREVIEW', 'SUBMITTED', 'COMMITTED', 'REJECTED', 'FAILED')",
            name="ck_sms_import_batches_status",
        ),
        CheckConstraint(
            "NOT (is_high_risk AND status = 'COMMITTED') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_sms_import_batches_high_risk_approval",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_import_batches_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "branch_id"],
            ["sms_branches.tenant_id", "sms_branches.id"],
            name="fk_sms_import_batches_branch_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_import_batches_created_by",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["submitted_by"],
            ["sms_users.id"],
            name="fk_sms_import_batches_submitted_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["approved_by"],
            ["sms_users.id"],
            name="fk_sms_import_batches_approved_by",
            ondelete="SET NULL",
        ),
        Index(
            "ix_sms_import_batches_scope_module_status",
            "tenant_id",
            "branch_id",
            "module_code",
            "status",
        ),
        Index("ix_sms_import_batches_creator_time", "created_by", "created_at"),
        Index("ix_sms_import_batches_checksum", "tenant_id", "import_type", "checksum"),
    )


class ImportRow(Base):
    """sms_import_rows table mapping."""

    __allow_unmapped__ = True

    id: Any
    batch_id: Any
    row_number: Any
    raw_data: Any
    normalized_data: Any
    validation_status: Any
    errors: Any
    target_entity_type: Any
    target_entity_id: Any

    __table__ = Table(
        "sms_import_rows",
        Base.metadata,
        uuid_pk(),
        uuid_col("batch_id", nullable=False),
        int_col("row_number", nullable=False),
        jsonb("raw_data"),
        jsonb("normalized_data"),
        text_col("validation_status", nullable=False),
        jsonb("errors", default="'[]'::jsonb"),
        varchar("proposed_action", 50),
        varchar("target_entity_type", 80),
        uuid_col("target_entity_id"),
        timestamp("processed_at"),
        timestamp("created_at", nullable=False, default_now=True),
        UniqueConstraint("batch_id", "row_number", name="uq_sms_import_rows_batch_row"),
        CheckConstraint("row_number > 0", name="ck_sms_import_rows_row_number"),
        CheckConstraint(
            "validation_status IN ('VALID', 'WARNING', 'REJECTED')",
            name="ck_sms_import_rows_validation_status",
        ),
        ForeignKeyConstraint(
            ["batch_id"],
            ["sms_import_batches.id"],
            name="fk_sms_import_rows_batch",
            ondelete="CASCADE",
        ),
        Index("ix_sms_import_rows_batch_validation", "batch_id", "validation_status"),
        Index(
            "ix_sms_import_rows_target",
            "target_entity_type",
            "target_entity_id",
            postgresql_where=text("target_entity_type IS NOT NULL OR target_entity_id IS NOT NULL"),
        ),
    )
