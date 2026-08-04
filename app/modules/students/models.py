"""Student and family foundation SQLAlchemy models."""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, UniqueConstraint, text

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    bool_col,
    date_col,
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class Student(Base):
    """sms_students table mapping."""

    __table__ = Table(
        "sms_students",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        varchar("student_number", 40, nullable=False),
        varchar("legal_name", 200, nullable=False),
        varchar("display_name", 200),
        date_col("date_of_birth", nullable=False),
        text_col("gender", nullable=False),
        varchar("student_mobile", 30),
        varchar("student_email", 320),
        jsonb("addresses"),
        varchar("preferred_language", 10),
        text_col("current_status", nullable=False),
        text_col("restricted_notes"),
        varchar("source_type", 40, nullable=False),
        varchar("source_reference", 180),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "student_number", name="uq_sms_students_tenant_student_number"),
        UniqueConstraint("tenant_id", "id", name="uq_sms_students_tenant_id_id"),
        CheckConstraint("current_status IN ('APPLICANT', 'ADMITTED', 'ACTIVE', 'INACTIVE', 'WITHDRAWN', 'COMPLETED')", name="ck_sms_students_current_status"),
        CheckConstraint("source_type IN ('MANUAL', 'IMPORT', 'MIGRATION', 'API', 'SYSTEM', 'AI_ASSISTED')", name="ck_sms_students_source_type"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_students_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_students_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_students_updated_by", ondelete="SET NULL"),
        Index("ix_sms_students_tenant_number", "tenant_id", "student_number"),
        Index("ix_sms_students_name_lower", "tenant_id", text("lower(legal_name)")),
        Index("ix_sms_students_mobile", "tenant_id", "student_mobile", postgresql_where=text("student_mobile IS NOT NULL")),
        Index("ix_sms_students_email_lower", "tenant_id", text("lower(student_email)"), postgresql_where=text("student_email IS NOT NULL")),
    )


class StudentAlias(Base):
    """sms_student_aliases table mapping."""

    __table__ = Table(
        "sms_student_aliases",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("branch_id"),
        varchar("alias_type", 50, nullable=False),
        varchar("alias_value", 120, nullable=False),
        date_col("valid_from"),
        date_col("valid_until"),
        varchar("source_reference", 180),
        uuid_col("created_by", nullable=False),
        timestamp("created_at", nullable=False, default_now=True),
        CheckConstraint("valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from", name="ck_sms_student_aliases_validity"),
        ForeignKeyConstraint(["tenant_id", "student_id"], ["sms_students.tenant_id", "sms_students.id"], name="fk_sms_student_aliases_student_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["sms_branches.tenant_id", "sms_branches.id"], name="fk_sms_student_aliases_branch_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_student_aliases_created_by", ondelete="RESTRICT"),
        Index("uq_sms_student_aliases_tenant_scope", "tenant_id", "alias_type", "alias_value", unique=True, postgresql_where=text("branch_id IS NULL")),
        Index("uq_sms_student_aliases_branch_scope", "tenant_id", "branch_id", "alias_type", "alias_value", unique=True, postgresql_where=text("branch_id IS NOT NULL")),
        Index("ix_sms_student_aliases_lookup", "tenant_id", "alias_type", "alias_value"),
        Index("ix_sms_student_aliases_student", "student_id"),
    )


class Enrollment(Base):
    """sms_enrollments table mapping."""

    __table__ = Table(
        "sms_enrollments",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("branch_id", nullable=False),
        uuid_col("academic_year_id", nullable=False),
        uuid_col("programme_id"),
        uuid_col("batch_id"),
        uuid_col("section_id"),
        varchar("admission_number", 60),
        varchar("roll_number", 60),
        varchar("year_level", 30, nullable=False),
        text_col("status", nullable=False, default="'DRAFT'"),
        date_col("joining_date", nullable=False),
        date_col("ending_date"),
        bool_col("is_current", default="true"),
        uuid_col("transfer_source_enrollment_id"),
        varchar("source_type", 40, nullable=False),
        varchar("source_reference", 180),
        jsonb("placement_data"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "id", name="uq_sms_enrollments_tenant_id_id"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'PROMOTED', 'TRANSFERRED', 'WITHDRAWN', 'COMPLETED', 'CLOSED')", name="ck_sms_enrollments_status"),
        CheckConstraint("source_type IN ('MANUAL', 'IMPORT', 'MIGRATION', 'API', 'SYSTEM')", name="ck_sms_enrollments_source_type"),
        CheckConstraint("ending_date IS NULL OR ending_date >= joining_date", name="ck_sms_enrollments_dates"),
        CheckConstraint("transfer_source_enrollment_id IS NULL OR transfer_source_enrollment_id <> id", name="ck_sms_enrollments_transfer_self"),
        ForeignKeyConstraint(["tenant_id", "student_id"], ["sms_students.tenant_id", "sms_students.id"], name="fk_sms_enrollments_student_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["sms_branches.tenant_id", "sms_branches.id"], name="fk_sms_enrollments_branch_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "academic_year_id"], ["sms_academic_years.tenant_id", "sms_academic_years.id"], name="fk_sms_enrollments_academic_year_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "programme_id"], ["sms_academic_programmes.tenant_id", "sms_academic_programmes.id"], name="fk_sms_enrollments_programme_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "branch_id", "batch_id"], ["sms_batches.tenant_id", "sms_batches.branch_id", "sms_batches.id"], name="fk_sms_enrollments_batch_hierarchy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "branch_id", "batch_id", "section_id"], ["sms_sections.tenant_id", "sms_sections.branch_id", "sms_sections.batch_id", "sms_sections.id"], name="fk_sms_enrollments_section_hierarchy", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "transfer_source_enrollment_id"], ["sms_enrollments.tenant_id", "sms_enrollments.id"], name="fk_sms_enrollments_transfer_source", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_enrollments_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_enrollments_updated_by", ondelete="SET NULL"),
        Index("uq_sms_enrollments_current_active", "student_id", unique=True, postgresql_where=text("is_current = true AND status = 'ACTIVE'")),
        Index("uq_sms_enrollments_branch_admission_number", "tenant_id", "branch_id", "admission_number", unique=True, postgresql_where=text("admission_number IS NOT NULL")),
        Index("uq_sms_enrollments_branch_year_roll_number", "tenant_id", "branch_id", "academic_year_id", "roll_number", unique=True, postgresql_where=text("roll_number IS NOT NULL")),
        Index("ix_sms_enrollments_scope_status", "tenant_id", "branch_id", "academic_year_id", "status"),
        Index("ix_sms_enrollments_student_year", "student_id", "academic_year_id"),
    )


class Guardian(Base):
    """sms_guardians table mapping."""

    __table__ = Table(
        "sms_guardians",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("portal_user_id"),
        varchar("full_name", 200, nullable=False),
        varchar("mobile", 30, nullable=False),
        varchar("email", 320),
        jsonb("address_data"),
        jsonb("identity_data"),
        text_col("verification_status", nullable=False, default="'UNVERIFIED'"),
        timestamp("verified_at"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        jsonb("preferences"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        UniqueConstraint("tenant_id", "id", name="uq_sms_guardians_tenant_id_id"),
        CheckConstraint("verification_status IN ('UNVERIFIED', 'PENDING', 'VERIFIED', 'REJECTED')", name="ck_sms_guardians_verification_status"),
        CheckConstraint("status IN ('ACTIVE', 'BLOCKED', 'INACTIVE')", name="ck_sms_guardians_status"),
        CheckConstraint("verification_status <> 'VERIFIED' OR verified_at IS NOT NULL", name="ck_sms_guardians_verified_at"),
        ForeignKeyConstraint(["tenant_id"], ["sms_tenants.id"], name="fk_sms_guardians_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "portal_user_id"], ["sms_users.tenant_id", "sms_users.id"], name="fk_sms_guardians_portal_user_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_guardians_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_guardians_updated_by", ondelete="SET NULL"),
        Index("uq_sms_guardians_tenant_portal_user", "tenant_id", "portal_user_id", unique=True, postgresql_where=text("portal_user_id IS NOT NULL")),
        Index("ix_sms_guardians_tenant_mobile", "tenant_id", "mobile"),
        Index("ix_sms_guardians_portal_user", "portal_user_id", postgresql_where=text("portal_user_id IS NOT NULL")),
        Index("ix_sms_guardians_tenant_status", "tenant_id", "status"),
    )


class StudentGuardianLink(Base):
    """sms_student_guardian_links table mapping."""

    __table__ = Table(
        "sms_student_guardian_links",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("student_id", nullable=False),
        uuid_col("guardian_id", nullable=False),
        varchar("relationship_type", 50, nullable=False),
        bool_col("is_primary", default="false"),
        bool_col("portal_access_enabled", default="false"),
        bool_col("notification_enabled", default="true"),
        bool_col("payment_enabled", default="false"),
        jsonb("preferences"),
        text_col("verification_status", nullable=False, default="'PENDING'"),
        timestamp("verified_at"),
        uuid_col("verified_by"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        timestamp("effective_from", nullable=False, default_now=True),
        timestamp("effective_until"),
        uuid_col("created_by", nullable=False),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint("relationship_type IN ('FATHER', 'MOTHER', 'LEGAL_GUARDIAN', 'RELATIVE', 'SPONSOR', 'OTHER')", name="ck_sms_student_guardian_links_relationship"),
        CheckConstraint("verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'REVOKED')", name="ck_sms_student_guardian_links_verification_status"),
        CheckConstraint("status IN ('ACTIVE', 'SUSPENDED', 'REVOKED')", name="ck_sms_student_guardian_links_status"),
        CheckConstraint("effective_until IS NULL OR effective_until > effective_from", name="ck_sms_student_guardian_links_validity"),
        CheckConstraint("verification_status <> 'VERIFIED' OR verified_at IS NOT NULL", name="ck_sms_student_guardian_links_verified_at"),
        ForeignKeyConstraint(["tenant_id", "student_id"], ["sms_students.tenant_id", "sms_students.id"], name="fk_sms_student_guardian_links_student_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "guardian_id"], ["sms_guardians.tenant_id", "sms_guardians.id"], name="fk_sms_student_guardian_links_guardian_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["verified_by"], ["sms_users.id"], name="fk_sms_student_guardian_links_verified_by", ondelete="SET NULL"),
        ForeignKeyConstraint(["created_by"], ["sms_users.id"], name="fk_sms_student_guardian_links_created_by", ondelete="RESTRICT"),
        ForeignKeyConstraint(["updated_by"], ["sms_users.id"], name="fk_sms_student_guardian_links_updated_by", ondelete="SET NULL"),
        Index("uq_sms_student_guardian_links_active", "student_id", "guardian_id", unique=True, postgresql_where=text("status IN ('ACTIVE', 'SUSPENDED') AND effective_until IS NULL")),
        Index("ix_sms_student_guardian_links_guardian_status", "guardian_id", "status"),
        Index("ix_sms_student_guardian_links_student_primary", "student_id", "is_primary"),
        Index("ix_sms_student_guardian_links_tenant_verification", "tenant_id", "verification_status"),
    )
