"""WhatsApp Notification Service: Template Formatting, Driver Routing, and Async Chunking."""

import asyncio
from datetime import datetime
import logging
from typing import Any
from uuid import UUID

import httpx
from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config.settings import settings
from app.modules.notifications.repository import NotificationsRepository

logger = logging.getLogger(__name__)


def _normalise_phone(raw: str | None) -> str | None:
    """Normalize phone number to international E.164 format (+91...)."""
    if not raw or raw == "N/A":
        return None
    cleaned = "".join(c for c in raw if c.isdigit() or c == "+")
    if not cleaned:
        return None
    if not cleaned.startswith("+"):
        if len(cleaned) == 10:
            cleaned = "+91" + cleaned
        else:
            cleaned = "+" + cleaned
    return cleaned


class WhatsAppNotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = NotificationsRepository(db)

    def _build_meta_payload(self, to_phone: str, template_name: str, parameters: list[str]) -> dict[str, Any]:
        """Format Meta-compliant template request payload."""
        return {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": str(p)} for p in parameters],
                    }
                ],
            },
        }

    async def _send_http_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Dispatch HTTP POST payload to local Simulator or Meta Cloud API."""
        mode = settings.whatsapp_mode.upper()
        if mode == "SIMULATOR":
            target_url = settings.simulator_url
            headers = {"Content-Type": "application/json"}
        else:
            phone_id = settings.meta_phone_number_id
            target_url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {settings.meta_access_token}",
                "Content-Type": "application/json",
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(target_url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def _dispatch_single_item(self, log_id: UUID, phone: str, template_name: str, params: list[str]) -> None:
        """Execute single notification dispatch and update status in database."""
        payload = self._build_meta_payload(phone, template_name, params)
        try:
            res = await self._send_http_request(payload)
            wamid = res.get("messages", [{}])[0].get("id", f"wamid.sim.{log_id}")
            self.repo.update_wamid_and_sent(log_id=log_id, wamid=wamid, status="SENT")
            logger.info(f"Notification {log_id} sent to {phone} (wamid: {wamid})")
        except Exception as err:
            logger.error(f"Failed to send notification {log_id} to {phone}: {err}")

    async def _dispatch_batch_chunked(self, items: list[dict[str, Any]], chunk_size: int = 15) -> None:
        """Process batch dispatches in async concurrent chunks of 15 requests."""
        for i in range(0, len(items), chunk_size):
            chunk = items[i : i + chunk_size]
            tasks = [
                self._dispatch_single_item(
                    log_id=item["log_id"],
                    phone=item["phone"],
                    template_name=item["template_name"],
                    params=item["params"],
                )
                for item in chunk
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(0.05) # 50ms rate-limiting breather

    # ------------------------------------------------------------------
    # EVENT DISPATCHERS
    # ------------------------------------------------------------------

    def _calculate_student_exam_summary(
        self, tenant_id: UUID, exam_id: UUID, student_id: UUID
    ) -> tuple[str, str, str, str]:
        """Dynamically computes mark details, total score, percentage, and final status."""
        rec_row = self.db.execute(
            text("SELECT subject_marks FROM sms_student_exam_records WHERE exam_id = :exam_id AND student_id = :student_id AND tenant_id = :tenant_id LIMIT 1"),
            {"exam_id": exam_id, "student_id": student_id, "tenant_id": tenant_id},
        ).fetchone()

        subject_marks = (rec_row.subject_marks if rec_row else {}) or {}

        sub_rows = self.db.execute(
            text("SELECT id, subject_id, subject_name, subject_code, maximum_marks, pass_marks FROM sms_exam_subjects WHERE exam_id = :exam_id"),
            {"exam_id": exam_id},
        ).fetchall()

        sub_map = {}
        for s in sub_rows:
            info = {"name": s.subject_name, "max": s.maximum_marks, "pass": s.pass_marks}
            sub_map[str(s.id)] = info
            if s.subject_code:
                sub_map[s.subject_code.upper()] = info
                sub_map[s.subject_code] = info
            if getattr(s, "subject_id", None):
                sub_map[str(s.subject_id)] = info

        master_subs = self.db.execute(
            text("SELECT id, subject_code, subject_name FROM sms_subjects WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).fetchall()
        for ms in master_subs:
            if str(ms.id) not in sub_map:
                sub_map[str(ms.id)] = {"name": ms.subject_name, "max": 100, "pass": 35}
            if ms.subject_code and ms.subject_code.upper() not in sub_map:
                sub_map[ms.subject_code.upper()] = {"name": ms.subject_name, "max": 100, "pass": 35}

        score_details = []
        total_obtained = 0.0
        total_max = 0.0
        absent_subs = []
        failed_subs = []
        attempted_count = 0

        for sub_key, score_val in subject_marks.items():
            try:
                score = float(score_val)
            except (ValueError, TypeError):
                continue

            sub_info = sub_map.get(str(sub_key)) or sub_map.get(str(sub_key).upper())
            sub_name = sub_info["name"] if sub_info else str(sub_key).capitalize()
            max_m = float(sub_info["max"]) if (sub_info and sub_info.get("max")) else 100.0
            pass_m = float(sub_info["pass"]) if (sub_info and sub_info.get("pass")) else 35.0

            if score < 0:
                status_str = "ABSENT" if score == -1 else "EXEMPTED"
                score_details.append(f"  • {sub_name}: [{status_str}]")
                if score == -1:
                    absent_subs.append(sub_name)
                continue

            attempted_count += 1
            is_pass = score >= pass_m
            if not is_pass:
                failed_subs.append(sub_name)

            total_obtained += score
            total_max += max_m
            score_details.append(f"  • {sub_name}: {score:g}/{max_m:g} -> {'PASSED' if is_pass else 'FAILED'}")

        pct = (total_obtained / total_max * 100) if total_max > 0 else 0.0

        if absent_subs:
            reasons = ", ".join(absent_subs[:2])
            final_status = f"FAILED (Absent in {len(absent_subs)} subjects)" if len(absent_subs) > 2 else f"FAILED (Absent in {reasons})"
        elif failed_subs:
            reasons = ", ".join(failed_subs[:2])
            final_status = f"FAILED (Failed in {len(failed_subs)} subjects)" if len(failed_subs) > 2 else f"FAILED (Failed in {reasons})"
        else:
            final_status = f"PASSED (Passed All {attempted_count} Subjects)" if attempted_count > 0 else "PASSED"

        mark_details_str = "\n".join(score_details) if score_details else "  (No mark details entered)"
        total_str = f"{total_obtained:g} / {total_max:g}"
        pct_str = f"{pct:.1f}"

        return mark_details_str, total_str, pct_str, final_status

    def send_exam_published_notifications(
        self, exam_id: UUID, tenant_id: UUID, branch_id: UUID | None, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Batch Queue: Dispatch exam result notifications to all enrolled students in published exam."""
        exam_row = self.db.execute(text("SELECT name, exam_date FROM sms_exams WHERE id = :id"), {"id": exam_id}).first()
        branch_row = self.db.execute(text("SELECT display_name FROM sms_branches WHERE id = :id"), {"id": branch_id}).first() if branch_id else None

        exam_name = exam_row.name if exam_row else "Term Assessment"
        exam_date = str(exam_row.exam_date) if exam_row else "2026-08-15"
        branch_name = branch_row.display_name if branch_row else "Main Campus"

        students_sql = """
        SELECT ser.student_id,
               COALESCE(s.display_name, s.legal_name) as student_name,
               COALESCE(g.mobile, s.student_mobile) as guardian_phone
        FROM sms_student_exam_records ser
        JOIN sms_students s ON s.id = ser.student_id
        LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = s.id AND sgl.is_primary = true
        LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id
        WHERE ser.exam_id = :exam_id
          AND ser.tenant_id = :tenant_id
        """
        rows = self.db.execute(text(students_sql), {"exam_id": exam_id, "tenant_id": tenant_id}).fetchall()
        print(f"[NOTIF] >>> Total students with exam records found: {len(rows)}")

        items_to_dispatch = []
        for r in rows:
            student_id = r.student_id
            student_name = r.student_name
            phone = _normalise_phone(r.guardian_phone)
            idempotency_key = f"EXAM_PUBLISHED:{exam_id}:{student_id}"

            if not phone:
                self.repo.create_log(
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    event_type="EXAM_PUBLISHED",
                    entity_id=str(exam_id),
                    student_id=student_id,
                    recipient_phone=None,
                    template_name=settings.template_exam_published,
                    idempotency_key=idempotency_key,
                    delivery_status="FAILED_MISSING_PHONE",
                    error_message="Student guardian mobile phone number is missing in profile",
                )
                continue

            mark_details, total_str, pct_str, final_status = self._calculate_student_exam_summary(tenant_id, exam_id, student_id)

            params = [
                student_name,
                exam_name,
                exam_date,
                mark_details,
                total_str,
                pct_str,
                final_status,
                branch_name,
            ]

            log = self.repo.create_log(
                tenant_id=tenant_id,
                branch_id=branch_id,
                event_type="EXAM_PUBLISHED",
                entity_id=str(exam_id),
                student_id=student_id,
                recipient_phone=phone,
                template_name=settings.template_exam_published,
                idempotency_key=idempotency_key,
                delivery_status="QUEUED",
            )
            items_to_dispatch.append({
                "log_id": log.id,
                "phone": phone,
                "template_name": settings.template_exam_published,
                "params": params,
            })

        if items_to_dispatch:
            background_tasks.add_task(self._dispatch_batch_chunked, items_to_dispatch)

        return {"queued_count": len(items_to_dispatch), "total_students": len(rows)}

    def send_single_student_correction_notification(
        self, exam_id: UUID, student_id: UUID, tenant_id: UUID, branch_id: UUID | None, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Single 1-to-1: Dispatch updated exam result notice to 1 student."""
        stu = self.db.execute(text("SELECT COALESCE(display_name, legal_name) as name FROM sms_students WHERE id = :id"), {"id": student_id}).first()
        g = self.db.execute(text("SELECT COALESCE(g.mobile, st.student_mobile) as mobile FROM sms_students st LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = st.id AND sgl.is_primary = true LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id WHERE st.id = :id"), {"id": student_id}).first()
        exam_row = self.db.execute(text("SELECT name, exam_date FROM sms_exams WHERE id = :id"), {"id": exam_id}).first()
        branch_row = self.db.execute(text("SELECT display_name FROM sms_branches WHERE id = :id"), {"id": branch_id}).first() if branch_id else None

        student_name = stu.name if stu else "Student"
        phone = _normalise_phone(g.mobile if g else None)
        exam_name = exam_row.name if exam_row else "Term Exam"
        exam_date = str(exam_row.exam_date) if exam_row else "2026-08-20"
        branch_name = branch_row.display_name if branch_row else "Main Campus"
        idempotency_key = f"SINGLE_CORRECTION:{exam_id}:{student_id}:v2"

        if not phone:
            self.repo.create_log(
                tenant_id=tenant_id,
                branch_id=branch_id,
                event_type="MARK_CORRECTION",
                entity_id=str(exam_id),
                student_id=student_id,
                recipient_phone=None,
                template_name=settings.template_mark_correction,
                idempotency_key=idempotency_key,
                delivery_status="FAILED_MISSING_PHONE",
                error_message="Student guardian mobile phone number is missing in profile",
            )
            return {"status": "FAILED_MISSING_PHONE"}

        mark_details, total_str, pct_str, final_status = self._calculate_student_exam_summary(tenant_id, exam_id, student_id)

        params = [
            student_name,
            exam_name,
            exam_date,
            mark_details,
            total_str,
            pct_str,
            final_status,
            branch_name,
        ]

        log = self.repo.create_log(
            tenant_id=tenant_id,
            branch_id=branch_id,
            event_type="MARK_CORRECTION",
            entity_id=str(exam_id),
            student_id=student_id,
            recipient_phone=phone,
            template_name=settings.template_mark_correction,
            idempotency_key=idempotency_key,
            delivery_status="QUEUED",
        )

        background_tasks.add_task(
            self._dispatch_single_item,
            log.id,
            phone,
            settings.template_mark_correction,
            params,
        )
        return {"status": "QUEUED", "log_id": str(log.id)}

    def send_fee_receipt_notification(
        self,
        payment_id: UUID,
        student_id: UUID,
        amount_paid: float,
        receipt_no: str,
        payment_mode: str | None,
        remaining_balance: float,
        payment_period_label: str | None,
        tenant_id: UUID,
        branch_id: UUID | None,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """Single 1-to-1: Dispatch fee payment receipt notice to 1 student."""
        stu = self.db.execute(text("SELECT COALESCE(display_name, legal_name) as name FROM sms_students WHERE id = :id"), {"id": student_id}).first()
        g = self.db.execute(text("SELECT COALESCE(g.mobile, st.student_mobile) as mobile FROM sms_students st LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = st.id AND sgl.is_primary = true LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id WHERE st.id = :id"), {"id": student_id}).first()
        branch_row = self.db.execute(text("SELECT display_name FROM sms_branches WHERE id = :id"), {"id": branch_id}).first() if branch_id else None

        student_name = stu.name if stu else "Student"
        phone = _normalise_phone(g.mobile if g else None)
        branch_name = branch_row.display_name if branch_row else "Main Campus"
        idempotency_key = f"FEE_RECEIPT:{payment_id}:{student_id}"

        if not phone:
            self.repo.create_log(
                tenant_id=tenant_id,
                branch_id=branch_id,
                event_type="FEE_RECEIPT",
                entity_id=str(payment_id),
                student_id=student_id,
                recipient_phone=None,
                template_name=settings.template_fee_receipt,
                idempotency_key=idempotency_key,
                delivery_status="FAILED_MISSING_PHONE",
                error_message="Student guardian mobile phone number is missing in profile",
            )
            return {"status": "FAILED_MISSING_PHONE"}

        today_str = str(datetime.now().date())
        period_text = payment_period_label if (payment_period_label and str(payment_period_label).strip().lower() not in ("none", "")) else "Tuition Fee Payment"
        params = [
            student_name,
            period_text,

            receipt_no,
            today_str,
            f"{amount_paid:,.2f}",
            payment_mode or "UPI / Bank Transfer",
            f"{remaining_balance:,.2f}",
            branch_name,
        ]

        log = self.repo.create_log(
            tenant_id=tenant_id,
            branch_id=branch_id,
            event_type="FEE_RECEIPT",
            entity_id=str(payment_id),
            student_id=student_id,
            recipient_phone=phone,
            template_name=settings.template_fee_receipt,
            idempotency_key=idempotency_key,
            delivery_status="QUEUED",
        )

        background_tasks.add_task(
            self._dispatch_single_item,
            log.id,
            phone,
            settings.template_fee_receipt,
            params,
        )
        return {"status": "QUEUED", "log_id": str(log.id)}

    def send_attendance_absent_notifications(
        self, section_id: UUID, section_name: str, absent_student_ids: list[UUID], date_str: str, tenant_id: UUID, branch_id: UUID | None, background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        """Batch Queue: Dispatch daily attendance absentee alerts to parents of absent students."""
        branch_row = self.db.execute(text("SELECT display_name FROM sms_branches WHERE id = :id"), {"id": branch_id}).first() if branch_id else None
        branch_name = branch_row.display_name if branch_row else "Main Campus"

        items_to_dispatch = []
        for student_id in absent_student_ids:
            stu = self.db.execute(text("SELECT COALESCE(display_name, legal_name) as name FROM sms_students WHERE id = :id"), {"id": student_id}).first()
            g = self.db.execute(text("SELECT COALESCE(g.mobile, st.student_mobile) as mobile FROM sms_students st LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = st.id AND sgl.is_primary = true LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id WHERE st.id = :id"), {"id": student_id}).first()

            student_name = stu.name if stu else "Student"
            phone = _normalise_phone(g.mobile if g else None)
            idempotency_key = f"ATTENDANCE_ABSENT:{section_id}:{date_str}:{student_id}"

            if not phone:
                self.repo.create_log(
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    event_type="ATTENDANCE_ABSENT",
                    entity_id=f"{section_id}:{date_str}",
                    student_id=student_id,
                    recipient_phone=None,
                    template_name=settings.template_attendance_absent,
                    idempotency_key=idempotency_key,
                    delivery_status="FAILED_MISSING_PHONE",
                    error_message="Student guardian mobile phone number is missing in profile",
                )
                continue

            params = [
                student_name,
                section_name,
                date_str,
                branch_name,
            ]

            log = self.repo.create_log(
                tenant_id=tenant_id,
                branch_id=branch_id,
                event_type="ATTENDANCE_ABSENT",
                entity_id=f"{section_id}:{date_str}",
                student_id=student_id,
                recipient_phone=phone,
                template_name=settings.template_attendance_absent,
                idempotency_key=idempotency_key,
                delivery_status="QUEUED",
            )
            items_to_dispatch.append({
                "log_id": log.id,
                "phone": phone,
                "template_name": settings.template_attendance_absent,
                "params": params,
            })

        if items_to_dispatch:
            background_tasks.add_task(self._dispatch_batch_chunked, items_to_dispatch)

        return {"queued_count": len(items_to_dispatch), "absent_count": len(absent_student_ids)}

