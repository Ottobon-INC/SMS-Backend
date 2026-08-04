"""Academic foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint, text

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    bool_col,
    date_col,
    int_col,
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class AcademicYear(Base):
    """sms_academic_years table mapping."""

    __table__ = Table(
        "sms_academic_years",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        varchar("code", 30, nullable=False),
        varchar("name", 100, nullable=False),
        date_col("starts_on", nullable=False),
        date_col("ends_on", nullable=False),
        text_col("status", nullable=False, default="'DRAFT'"),
        bool_col("is_default", default="false"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "code", name="uq_sms_academic_years_tenant_code"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_academic_years_tenant_id_id"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED')", name="ck_sms_academic_years_status"),
        CheckConstraint("ends_on > starts_on", name="ck_sms_academic_years_dates"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_academic_years_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_academic_years_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_academic_years_updated_by", ondelete="SET NULL"),
        Index("uq_sms_academic_years_default_active", "tenant_id", unique=True, postgresql_where=text("is_default = true AND status = 'ACTIVE'")),
        Index("ix_sms_academic_years_tenant_status", "tenant_id", "status"),
        Index("ix_sms_academic_years_date_range", "starts_on", "ends_on"),
    )


class AcademicProgramme(Base):
    """sms_academic_programmes table mapping."""

    __table__ = Table(
        "sms_academic_programmes",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        varchar("programme_code", 40, nullable=False),
        varchar("programme_name", 150, nullable=False),
        varchar("stream_code", 30),
        varchar("coaching_track", 80),
        int_col("duration_years"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        jsonb("metadata"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "programme_code", name="uq_sms_academic_programmes_tenant_code"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_academic_programmes_tenant_id_id"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_sms_academic_programmes_status"),
        CheckConstraint("duration_years IS NULL OR duration_years > 0", name="ck_sms_academic_programmes_duration"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_academic_programmes_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_academic_programmes_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_academic_programmes_updated_by", ondelete="SET NULL"),
        Index("ix_sms_academic_programmes_tenant_status", "tenant_id", "status"),
        Index("ix_sms_academic_programmes_stream", "stream_code", postgresql_where=text("stream_code IS NOT NULL")),
    )


class Batch(Base):
    """sms_batches table mapping."""

    __table__ = Table(
        "sms_batches",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        uuid_col("programme_id", nullable=False),
        varchar("batch_code", 40, nullable=False),
        varchar("batch_name", 150, nullable=False),
        varchar("year_level", 30, nullable=False),
        text_col("status", nullable=False, default="'ACTIVE'"),
        jsonb("metadata"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "branch_id", "academic_year_id", "batch_code", name="uq_sms_batches_scope_code"),
        UniqueConstraint("tenant_id", "branch_id", "id", name="uq_sms_batches_tenant_branch_id"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE', 'CLOSED')", name="ck_sms_batches_status"),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["sms_branches.tenant_id", "sms_branches.id"], name="fk_sms_batches_branch_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "academic_year_id"], ["sms_academic_years.tenant_id", "sms_academic_years.id"], name="fk_sms_batches_academic_year_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "programme_id"], ["sms_academic_programmes.tenant_id", "sms_academic_programmes.id"], name="fk_sms_batches_programme_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_batches_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_batches_updated_by", ondelete="SET NULL"),
        Index("ix_sms_batches_branch_year_status", "branch_id", "academic_year_id", "status"),
        Index("ix_sms_batches_programme", "programme_id"),
    )


class Section(Base):
    """sms_sections table mapping."""

    __table__ = Table(
        "sms_sections",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("batch_id", nullable=False),
        varchar("section_code", 30, nullable=False),
        varchar("section_name", 100, nullable=False),
        int_col("capacity"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        jsonb("metadata"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("batch_id", "section_code", name="uq_sms_sections_batch_code"),
        UniqueConstraint("tenant_id", "branch_id", "id", name="uq_sms_sections_tenant_branch_id"),
        UniqueConstraint("tenant_id", "branch_id", "batch_id", "id", name="uq_sms_sections_hierarchy_id"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE', 'CLOSED')", name="ck_sms_sections_status"),
        CheckConstraint("capacity IS NULL OR capacity >= 0", name="ck_sms_sections_capacity"),
        ForeignKeyConstraint(["tenant_id", "branch_id", "batch_id"], ["sms_batches.tenant_id", "sms_batches.branch_id", "sms_batches.id"], name="fk_sms_sections_batch_hierarchy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_sections_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_sections_updated_by", ondelete="SET NULL"),
        Index("ix_sms_sections_branch_status", "branch_id", "status"),
        Index("ix_sms_sections_batch", "batch_id"),
    )


class Subject(Base):
    """sms_subjects table mapping."""

    __table__ = Table(
        "sms_subjects",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        varchar("subject_code", 40, nullable=False),
        varchar("subject_name", 150, nullable=False),
        varchar("subject_type", 40),
        text_col("status", nullable=False, default="'ACTIVE'"),
        jsonb("metadata"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "subject_code", name="uq_sms_subjects_tenant_code"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_subjects_tenant_id_id"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_sms_subjects_status"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_subjects_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_subjects_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_subjects_updated_by", ondelete="SET NULL"),
        Index("ix_sms_subjects_tenant_status", "tenant_id", "status"),
        Index("ix_sms_subjects_name_lower", "tenant_id", text("lower(subject_name)")),
    )


class SectionSubject(Base):
    """sms_section_subjects table mapping."""

    __table__ = Table(
        "sms_section_subjects",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("section_id", nullable=False),
        uuid_col("subject_id", nullable=False),
        text_col("status", nullable=False, default="'ACTIVE'"),
        date_col("effective_from"),
        date_col("effective_until"),
        jsonb("metadata"),
        uuid_col("created_by", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_sms_section_subjects_status"),
        CheckConstraint("effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from", name="ck_sms_section_subjects_effective_dates"),
        ForeignKeyConstraint(["tenant_id", "branch_id", "section_id"], ["sms_sections.tenant_id", "sms_sections.branch_id", "sms_sections.id"], name="fk_sms_section_subjects_section_hierarchy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "subject_id"], ["sms_subjects.tenant_id", "sms_subjects.id"], name="fk_sms_section_subjects_subject_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_section_subjects_created_by", ondelete="RESTRICT"),
        Index("uq_sms_section_subjects_active", "section_id", "subject_id", unique=True, postgresql_where=text("status = 'ACTIVE' AND effective_until IS NULL")),
        Index("ix_sms_section_subjects_section_status", "section_id", "status"),
        Index("ix_sms_section_subjects_subject_status", "subject_id", "status"),
    )
