"""FastAPI Router for WhatsApp Webhooks, Handshakes, and Notification Audit Logs."""

import asyncio
import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.core.database.session import get_session_factory
from app.core.security.context import RequestContext
from app.core.security.dependencies import require_any_permission, require_tenant_scope
from app.modules.notifications.models import NotificationLog
from app.modules.notifications.repository import NotificationsRepository
from app.modules.notifications.schemas import (
    DispatchProgressResponse,
    MetaWebhookPayload,
    NotificationLogRead,
)
from app.modules.notifications.service import WhatsAppNotificationService, _normalise_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Notifications"])


def get_db():
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@router.get("/webhook")
def verify_meta_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge"),
):
    """Meta Webhook Registration Handshake verification endpoint."""
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        logger.info("Meta Webhook verification succeeded!")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Meta Webhook verification failed.")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid verification token")


@router.post("/webhook")
def receive_meta_webhook_callbacks(
    payload: MetaWebhookPayload,
    db: Session = Depends(get_db),
):
    """Receive async delivery status callbacks (sent -> delivered -> read) from Meta / Simulator."""
    repo = NotificationsRepository(db)

    for entry in payload.entry:
        for change in entry.changes:
            for st in change.value.statuses:
                wamid = st.id
                status_str = st.status
                repo.update_status_by_wamid(wamid=wamid, status=status_str)
                logger.info(f"Updated status for {wamid} to {status_str.upper()}")

    return {"status": "success"}


@router.get("/logs", response_model=list[NotificationLogRead])
def list_notification_logs(
    branch_id: UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({"notification.view"})),
):
    """List notification outbox logs with RBAC branch filtering."""
    repo = NotificationsRepository(db)
    return repo.list_logs(tenant_id=context.tenant_id, branch_id=branch_id, limit=limit)


@router.get("/progress/{entity_id}", response_model=DispatchProgressResponse)
def get_dispatch_progress(
    entity_id: str,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({"notification.view"})),
):
    """Query completion percentage and ongoing state for an assessment or section."""
    repo = NotificationsRepository(db)
    prog = repo.get_progress(entity_id)

    # Check if exam is published
    sql = "SELECT status FROM sms_exams WHERE id::text = :id"
    res = db.execute(text(sql), {"id": entity_id}).first()
    exam_status = res.status if res else "UNKNOWN"

    return {
        "entity_id": entity_id,
        "status": exam_status,
        "total_notifications": prog["total_notifications"],
        "completed_notifications": prog["completed_notifications"],
        "failed_notifications": prog["failed_notifications"],
        "missing_phone_notifications": prog["missing_phone_notifications"],
        "progress_percentage": prog["progress_percentage"],
        "is_ongoing": prog["is_ongoing"],
    }


class UpdateGuardianPhoneRequest(BaseModel):
    student_id: UUID
    mobile: str


@router.post("/update-guardian-phone")
def update_guardian_phone(
    payload: UpdateGuardianPhoneRequest,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({"notification.view"})),
):
    """Save or update guardian mobile phone number for a student."""
    link = db.execute(
        text(
            "SELECT guardian_id FROM sms_student_guardian_links "
            "WHERE student_id = :id AND is_primary = true"
        ),
        {"id": payload.student_id},
    ).first()

    if link and link.guardian_id:
        db.execute(
            text("UPDATE sms_guardians SET mobile = :mobile WHERE id = :id"),
            {"mobile": payload.mobile, "id": link.guardian_id},
        )
    else:
        gid = uuid.uuid4()
        db.execute(
            text(
                "INSERT INTO sms_guardians "
                "(id, full_name, mobile) VALUES (:id, 'Primary Guardian', :mobile)"
            ),
            {"id": gid, "mobile": payload.mobile},
        )
        db.execute(
            text(
                "INSERT INTO sms_student_guardian_links "
                "(student_id, guardian_id, is_primary) VALUES (:sid, :gid, true)"
            ),
            {"sid": payload.student_id, "gid": gid},
        )

    db.execute(
        text("UPDATE sms_students SET student_mobile = :mobile WHERE id = :id"),
        {"mobile": payload.mobile, "id": payload.student_id},
    )
    db.commit()

    # Auto Re-dispatch any pending FAILED_MISSING_PHONE notifications for this student
    re_dispatched_count = 0
    clean_phone = _normalise_phone(payload.mobile)
    if clean_phone:
        pending_logs = (
            db.query(NotificationLog)
            .filter(
                NotificationLog.student_id == payload.student_id,
                NotificationLog.delivery_status == "FAILED_MISSING_PHONE",
            )
            .all()
        )
        if pending_logs:
            notif_svc = WhatsAppNotificationService(db)
            for log in pending_logs:
                log.recipient_phone = clean_phone
                log.delivery_status = "QUEUED"
                log.error_message = None
                db.commit()

                # Dispatch async
                try:
                    asyncio.run(
                        notif_svc._dispatch_single_item(
                            log_id=log.id,
                            phone=clean_phone,
                            template_name=log.template_name,
                            params=[
                                "Student Parent",
                                "School Alert Notice",
                                "2026-08-18",
                                "Notice Details",
                                "100",
                                "100",
                                "PASSED",
                                "Main Campus",
                            ],
                        )
                    )
                    re_dispatched_count += 1
                except Exception as dispatch_err:
                    logger.error(f"Re-dispatch error for log {log.id}: {dispatch_err}")

    return {
        "status": "success",
        "mobile": payload.mobile,
        "re_dispatched_count": re_dispatched_count,
    }
