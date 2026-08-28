"""SQLAlchemy models for sms_notification_logs outbox tracking."""

from sqlalchemy import CheckConstraint, Table

from app.shared.models.base import Base
from app.shared.models.foundation_columns import (
    jsonb,
    text_col,
    timestamp,
    uuid_col,
    uuid_pk,
    varchar,
)


class NotificationLog(Base):
    """sms_notification_logs table mapping."""

    __table__ = Table(
        "sms_notification_logs",
        Base.metadata,
        uuid_pk(),
        uuid_col("tenant_id", nullable=False),
        uuid_col("branch_id", nullable=True),
        varchar(
            "event_type", 50, nullable=False
        ),  # EXAM_PUBLISHED, MARK_CORRECTION, FEE_RECEIPT, ATTENDANCE_ABSENT
        varchar("entity_id", 100, nullable=False),  # Exam ID, Payment ID, Section ID
        uuid_col("student_id", nullable=True),
        varchar("recipient_phone", 30, nullable=True),
        varchar("template_name", 100, nullable=False),
        varchar("idempotency_key", 150, nullable=False),
        varchar("provider_message_id", 150, nullable=True),
        varchar("delivery_status", 30, nullable=False, default="'QUEUED'"),
        text_col("error_message", nullable=True),
        jsonb("payload_data", nullable=True, default=None),
        timestamp("sent_at", nullable=True),
        timestamp("delivered_at", nullable=True),
        timestamp("read_at", nullable=True),
        timestamp("created_at", nullable=False, default_now=True),
        timestamp("updated_at", nullable=False, default_now=True),
        CheckConstraint(
            "delivery_status IN ('QUEUED', 'SENT', 'DELIVERED', 'READ', 'FAILED', 'FAILED_MISSING_PHONE')",
            name="sms_notification_logs_status_check",
        ),
    )
