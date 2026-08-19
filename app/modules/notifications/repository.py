"""Database repository for sms_notification_logs table."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.modules.notifications.models import NotificationLog


class NotificationsRepository:
    def __init__(self, db: Session):
        self.db = db

    def ensure_table_exists(self) -> None:
        """Create sms_notification_logs table if it does not exist."""
        sql = """
        CREATE TABLE IF NOT EXISTS sms_notification_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            branch_id UUID,
            event_type VARCHAR(50) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            student_id UUID,
            recipient_phone VARCHAR(30),
            template_name VARCHAR(100) NOT NULL,
            idempotency_key VARCHAR(150) NOT NULL,
            provider_message_id VARCHAR(150),
            delivery_status VARCHAR(30) NOT NULL DEFAULT 'QUEUED',
            error_message TEXT,
            payload_data JSONB,
            sent_at TIMESTAMP WITH TIME ZONE,
            delivered_at TIMESTAMP WITH TIME ZONE,
            read_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        self.db.execute(text(sql))
        self.db.commit()

    def create_log(
        self,
        tenant_id: UUID,
        branch_id: UUID | None,
        event_type: str,
        entity_id: str,
        student_id: UUID | None,
        recipient_phone: str | None,
        template_name: str,
        idempotency_key: str,
        delivery_status: str = "QUEUED",
        error_message: str | None = None,
        payload_data: dict[str, Any] | None = None,
    ) -> NotificationLog:
        """Insert a notification log record into sms_notification_logs."""
        self.ensure_table_exists()
        
        # Check if record with idempotency_key already exists
        existing = (
            self.db.query(NotificationLog)
            .filter(NotificationLog.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

        log = NotificationLog(
            tenant_id=tenant_id,
            branch_id=branch_id,
            event_type=event_type,
            entity_id=entity_id,
            student_id=student_id,
            recipient_phone=recipient_phone,
            template_name=template_name,
            idempotency_key=idempotency_key,
            delivery_status=delivery_status,
            error_message=error_message,
            payload_data=payload_data,
        )
        self.db.add(log)
        self.db.flush()
        log_id = log.id
        self.db.commit()
        print(f"[REPO] >>> create_log committed: id={log_id}, student_id={student_id}, status={delivery_status}, phone={recipient_phone}")
        # Re-fetch to avoid psycopg3 prepared-statement cache issues with db.refresh()
        return self.db.query(NotificationLog).filter(NotificationLog.id == log_id).first()


    def update_wamid_and_sent(self, log_id: UUID, wamid: str, status: str = "SENT") -> None:
        """Update provider_message_id (wamid) and sent_at timestamp."""
        log = self.db.query(NotificationLog).filter(NotificationLog.id == log_id).first()
        if log:
            log.provider_message_id = wamid
            log.delivery_status = status
            log.sent_at = datetime.now(timezone.utc)
            self.db.commit()

    def update_status_by_wamid(self, wamid: str, status: str) -> None:
        """Update delivery status (SENT, DELIVERED, READ, FAILED) based on provider_message_id."""
        log = self.db.query(NotificationLog).filter(NotificationLog.provider_message_id == wamid).first()
        if log:
            now = datetime.now(timezone.utc)
            log.delivery_status = status.upper()
            if status.lower() == "delivered":
                log.delivered_at = now
            elif status.lower() == "read":
                log.read_at = now
            elif status.lower() == "failed":
                log.error_message = "Delivery failed reported by Meta"
            self.db.commit()

    def get_progress(self, entity_id: str) -> dict[str, Any]:
        """Query completion and missing phone counts for progress tracking."""
        from datetime import timedelta
        self.ensure_table_exists()

        logs = self.db.query(NotificationLog).filter(NotificationLog.entity_id == entity_id).all()
        total = len(logs)
        completed = sum(1 for l in logs if l.delivery_status in ["SENT", "DELIVERED", "READ", "FAILED", "FAILED_MISSING_PHONE"])
        failed = sum(1 for l in logs if l.delivery_status == "FAILED")
        missing_phone = sum(1 for l in logs if l.delivery_status == "FAILED_MISSING_PHONE")
        queued_logs = [l for l in logs if l.delivery_status == "QUEUED"]

        # is_ongoing = True only if there are QUEUED logs created within the last 5 minutes
        # (i.e. actively dispatching). Stale QUEUED logs from a crashed dispatch = not ongoing.
        now = datetime.now(timezone.utc)
        stale_threshold = timedelta(minutes=5)
        ongoing = any(
            l.created_at and (now - l.created_at.replace(tzinfo=timezone.utc)).total_seconds() < stale_threshold.total_seconds()
            for l in queued_logs
        )

        pct = round((completed / total) * 100, 1) if total > 0 else 100.0
        return {
            "entity_id": entity_id,
            "total_notifications": total,
            "completed_notifications": completed,
            "failed_notifications": failed,
            "missing_phone_notifications": missing_phone,
            "progress_percentage": pct,
            "is_ongoing": ongoing,
        }


    def list_logs(self, tenant_id: UUID, branch_id: UUID | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """List notification logs with enriched student details and RBAC branch filtering."""
        self.ensure_table_exists()
        sql = """
        SELECT
            l.id,
            l.tenant_id,
            l.branch_id,
            l.event_type,
            l.entity_id,
            l.student_id,
            COALESCE(st.display_name, st.legal_name) AS student_name,
            st.student_number,
            (
                SELECT sec.section_name
                FROM sms_enrollments e
                JOIN sms_sections sec ON sec.id = e.section_id
                WHERE e.student_id = st.id
                LIMIT 1
            ) AS section_name,
            l.recipient_phone,
            l.template_name,
            l.idempotency_key,
            l.provider_message_id,
            l.delivery_status,
            l.error_message,
            l.sent_at,
            l.delivered_at,
            l.read_at,
            l.created_at
        FROM sms_notification_logs l
        LEFT JOIN sms_students st ON st.id = l.student_id
        WHERE l.tenant_id = :tenant_id
          AND (
              :has_branch = false OR
              l.branch_id = :branch_id OR
              EXISTS (SELECT 1 FROM sms_enrollments e WHERE e.student_id = st.id AND e.branch_id = :branch_id)
          )
        ORDER BY l.created_at DESC
        LIMIT :limit
        """
        rows = self.db.execute(text(sql), {
            "tenant_id": tenant_id,
            "has_branch": branch_id is not None,
            "branch_id": branch_id,
            "limit": limit,
        }).mappings().all()
        return [dict(r) for r in rows]
