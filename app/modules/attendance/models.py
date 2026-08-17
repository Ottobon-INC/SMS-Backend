"""Attendance module SQLAlchemy models."""

# mypy: ignore-errors

from typing import Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint
from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    date_col,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
)


class AttendanceSession(Base):
    """sms_attendance_sessions table mapping."""

    id: Any
    tenant_id: Any
    branch_id: Any
    academic_year_id: Any
    section_id: Any
    attendance_date: Any
    status: Any
    opened_by: Any
    submitted_by: Any
    submitted_at: Any
    finalized_by: Any
    finalized_at: Any
    created_at: Any
    updated_at: Any

    __table__ = Table(
        "sms_attendance_sessions",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        uuid_col("section_id", nullable=False),
        date_col("attendance_date", nullable=False),
        text_col("status", nullable=False, default="'DRAFT'"),
        uuid_col("opened_by", nullable=False),
        uuid_col("submitted_by"),
        timestamp("submitted_at", nullable=True),
        uuid_col("finalized_by"),
        timestamp("finalized_at", nullable=True),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "branch_id", "section_id", "attendance_date", name="uq_sms_attendance_sessions_scope"),
        CheckConstraint("status IN ('DRAFT', 'SUBMITTED', 'FINALIZED')", name="ck_sms_attendance_sessions_status"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_attendance_sessions_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["branch_id"], ["sms_branches.id"], name="fk_sms_attendance_sessions_branch", ondelete="RESTRICT"),
        ForeignKeyConstraint(["academic_year_id"], ["sms_academic_years.id"], name="fk_sms_attendance_sessions_academic_year", ondelete="RESTRICT"),
        ForeignKeyConstraint(["section_id"], ["sms_sections.id"], name="fk_sms_attendance_sessions_section", ondelete="RESTRICT"),
        ForeignKeyConstraint(["opened_by"], ["sms_users.id"], name="fk_sms_attendance_sessions_opened_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["submitted_by"], ["sms_users.id"], name="fk_sms_attendance_sessions_submitted_by", ondelete="SET NULL"),
        ForeignKeyConstraint(["finalized_by"], ["sms_users.id"], name="fk_sms_attendance_sessions_finalized_by", ondelete="SET NULL"),
        Index("ix_sms_attendance_sessions_date_branch", "attendance_date", "branch_id"),
        Index("ix_sms_attendance_sessions_status", "status"),
    )


class AttendanceRecord(Base):
    """sms_attendance_records table mapping."""

    id: Any
    tenant_id: Any
    branch_id: Any
    session_id: Any
    enrollment_id: Any
    attendance_status: Any
    note: Any
    marked_by: Any
    marked_at: Any
    created_at: Any
    updated_at: Any

    __table__ = Table(
        "sms_attendance_records",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("session_id", nullable=False),
        uuid_col("enrollment_id", nullable=False),
        text_col("attendance_status", nullable=False),
        text_col("note"),
        uuid_col("marked_by", nullable=False),
        timestamp("marked_at", nullable=False, default_now=True),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("session_id", "enrollment_id", name="uq_sms_attendance_records_session_enrollment"),
        CheckConstraint("attendance_status IN ('PRESENT', 'ABSENT', 'LEAVE')", name="ck_sms_attendance_records_status"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_attendance_records_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["branch_id"], ["sms_branches.id"], name="fk_sms_attendance_records_branch", ondelete="RESTRICT"),
        ForeignKeyConstraint(["session_id"], ["sms_attendance_sessions.id"], name="fk_sms_attendance_records_session", ondelete="CASCADE"),
        ForeignKeyConstraint(["enrollment_id"], ["sms_enrollments.id"], name="fk_sms_attendance_records_enrollment", ondelete="RESTRICT"),
        ForeignKeyConstraint(["marked_by"], ["sms_users.id"], name="fk_sms_attendance_records_marked_by", ondelete="RESTRICT"),
        Index("ix_sms_attendance_records_session", "session_id"),
        Index("ix_sms_attendance_records_enrollment", "enrollment_id"),
    )
