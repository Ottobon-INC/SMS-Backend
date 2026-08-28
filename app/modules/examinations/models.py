"""Examinations SQLAlchemy models matching database schema."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint, text

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    date_col,
    int_col,
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class Exam(Base):
    """sms_exams table mapping."""

    __table__ = Table(
        "sms_exams",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=True),
        varchar("scope", 30, nullable=False),
        jsonb("branch_ids", nullable=True, default=None),
        jsonb("excluded_branch_ids", nullable=True, default=None),
        jsonb("exemption_reasons", nullable=True, default=None),
        uuid_col("academic_year_id", nullable=False),
        uuid_col("programme_id", nullable=False),
        jsonb("programme_ids", nullable=True, default=None),
        varchar("name", 150, nullable=False),
        varchar("type", 50, nullable=False),
        date_col("exam_date", nullable=False),
        date_col("marks_entry_deadline", nullable=True),
        varchar("status", 30, nullable=False, default="'DRAFT'"),
        text_col("return_reason", nullable=True),
        timestamp("published_at", nullable=True),
        uuid_col("published_by", nullable=True),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by", nullable=True),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "scope IN ('SINGLE_BRANCH', 'ALL_BRANCHES', 'SELECTED_BRANCHES')",
            name="sms_exams_scope_check",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'RETURNED_FOR_CORRECTION', 'PUBLISHED')",
            name="sms_exams_status_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id"], ["sms_tenants.id"], name="fk_sms_exams_tenant", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["branch_id"], ["sms_branches.id"], name="fk_sms_exams_branch", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["academic_year_id"],
            ["sms_academic_years.id"],
            name="fk_sms_exams_academic_year",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["programme_id"],
            ["sms_academic_programmes.id"],
            name="fk_sms_exams_programme",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["published_by"],
            ["sms_users.id"],
            name="fk_sms_exams_published_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["created_by"], ["sms_users.id"], name="fk_sms_exams_created_by", ondelete="RESTRICT"
        ),
        ForeignKeyConstraint(
            ["updated_by"], ["sms_users.id"], name="fk_sms_exams_updated_by", ondelete="SET NULL"
        ),
        Index("ix_sms_exams_tenant_status", "tenant_id", "status"),
        Index("ix_sms_exams_branch", "branch_id", postgresql_where=text("branch_id IS NOT NULL")),
        Index("ix_sms_exams_date_prog", "exam_date", "programme_id"),
    )


class ExamSubject(Base):
    """sms_exam_subjects table mapping."""

    __table__ = Table(
        "sms_exam_subjects",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("exam_id", nullable=False),
        uuid_col("subject_id", nullable=False),
        varchar("subject_name", 150, nullable=False),
        varchar("subject_code", 40, nullable=False),
        int_col("maximum_marks", nullable=False),
        int_col("pass_marks", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        UniqueConstraint("exam_id", "subject_id", name="uq_sms_exam_subjects_exam_subject"),
        CheckConstraint("maximum_marks > 0", name="sms_exam_subjects_maximum_marks_check"),
        CheckConstraint("pass_marks >= 0", name="sms_exam_subjects_pass_marks_check"),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_exam_subjects_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["exam_id"], ["sms_exams.id"], name="fk_sms_exam_subjects_exam", ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["subject_id"],
            ["sms_subjects.id"],
            name="fk_sms_exam_subjects_subject",
            ondelete="RESTRICT",
        ),
        Index("ix_sms_exam_subjects_exam_id", "exam_id"),
    )


class StudentExamRecord(Base):
    """sms_student_exam_records table mapping."""

    __table__ = Table(
        "sms_student_exam_records",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("exam_id", nullable=False),
        uuid_col("enrollment_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("section_id", nullable=False),
        jsonb("subject_marks", nullable=False, default="'{}'::jsonb"),
        varchar("status", 30, nullable=False, default="'DRAFT'"),
        uuid_col("entered_by", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("exam_id", "student_id", name="uq_sms_student_exam_records_exam_student"),
        CheckConstraint(
            "status IN ('DRAFT', 'SUBMITTED', 'RETURNED_FOR_CORRECTION', 'PUBLISHED')",
            name="sms_student_exam_records_status_check",
        ),
        ForeignKeyConstraint(
            ["tenant_id"],
            ["sms_tenants.id"],
            name="fk_sms_student_exam_records_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["exam_id"],
            ["sms_exams.id"],
            name="fk_sms_student_exam_records_exam",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["enrollment_id"],
            ["sms_enrollments.id"],
            name="fk_sms_student_exam_records_enrollment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["student_id"],
            ["sms_students.id"],
            name="fk_sms_student_exam_records_student",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["section_id"],
            ["sms_sections.id"],
            name="fk_sms_student_exam_records_section",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["entered_by"],
            ["sms_users.id"],
            name="fk_sms_student_exam_records_entered_by",
            ondelete="RESTRICT",
        ),
        Index("ix_sms_student_exam_records_exam_section", "exam_id", "section_id"),
        Index("ix_sms_student_exam_records_student", "student_id"),
    )
