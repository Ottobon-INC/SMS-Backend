"""Authentication-owned extension SQLAlchemy models.

These tables are intentionally outside the locked 26-table foundation. They
must be created manually through reviewed SQL before password login or signup
requests can be used.
"""

# mypy: ignore-errors

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Table, text

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


class UserCredential(Base):
    """sms_user_credentials table mapping for backend-owned password login."""

    __table__ = Table(
        "sms_user_credentials",
        Base.metadata,
        uuid_pk(),
        uuid_col("user_id", nullable=False),
        varchar("login_identifier", 320, nullable=False),
        varchar("login_identifier_normalized", 320, nullable=False),
        text_col("password_hash", nullable=False),
        text_col("password_salt", nullable=False),
        varchar("password_algorithm", 80, nullable=False, default="'PBKDF2_SHA256'"),
        int_col("password_iterations", nullable=False, default="390000"),
        text_col("status", nullable=False, default="'ACTIVE'"),
        bool_col("must_change_password", default="false"),
        int_col("failed_login_count", nullable=False, default="0"),
        timestamp("locked_until"),
        timestamp("last_login_at"),
        timestamp("password_changed_at", nullable=False, default_now=True),
        uuid_col("created_by"),
        uuid_col("updated_by"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "password_algorithm IN ('PBKDF2_SHA256')",
            name="ck_sms_user_credentials_password_algorithm",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'DISABLED', 'LOCKED', 'PASSWORD_RESET_REQUIRED')",
            name="ck_sms_user_credentials_status",
        ),
        CheckConstraint(
            "password_iterations >= 210000",
            name="ck_sms_user_credentials_iterations_minimum",
        ),
        CheckConstraint(
            "failed_login_count >= 0",
            name="ck_sms_user_credentials_failed_count_nonnegative",
        ),
        ForeignKeyConstraint(
            ["user_id"],
            ["sms_users.id"],
            name="fk_sms_user_credentials_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["created_by"],
            ["sms_users.id"],
            name="fk_sms_user_credentials_created_by",
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["updated_by"],
            ["sms_users.id"],
            name="fk_sms_user_credentials_updated_by",
            ondelete="SET NULL",
        ),
        Index(
            "uq_sms_user_credentials_login_identifier_active",
            "login_identifier_normalized",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'LOCKED', 'PASSWORD_RESET_REQUIRED')"),
        ),
        Index(
            "uq_sms_user_credentials_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('ACTIVE', 'LOCKED', 'PASSWORD_RESET_REQUIRED')"),
        ),
        Index("ix_sms_user_credentials_user_status", "user_id", "status"),
    )


class SignupRequest(Base):
    """sms_signup_requests table mapping for public account-request intake."""

    __table__ = Table(
        "sms_signup_requests",
        Base.metadata,
        uuid_pk(),
        varchar("requested_portal", 40, nullable=False),
        varchar("full_name", 200, nullable=False),
        varchar("email", 320, nullable=False),
        varchar("mobile", 30),
        varchar("institution_name", 200),
        varchar("branch_name", 200),
        text_col("message"),
        text_col("status", nullable=False, default="'PENDING'"),
        jsonb("metadata"),
        uuid_col("reviewed_by"),
        timestamp("reviewed_at"),
        text_col("review_notes"),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "requested_portal IN ('institution', 'branch', 'office', 'parent', 'platform')",
            name="ck_sms_signup_requests_requested_portal",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'REVIEWED', 'APPROVED', 'REJECTED')",
            name="ck_sms_signup_requests_status",
        ),
        ForeignKeyConstraint(
            ["reviewed_by"],
            ["sms_users.id"],
            name="fk_sms_signup_requests_reviewed_by",
            ondelete="SET NULL",
        ),
        Index(
            "uq_sms_signup_requests_email_pending",
            text("lower(email)"),
            "requested_portal",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
        Index("ix_sms_signup_requests_status_created", "status", "created_at"),
    )
