"""Read-only dashboard repository queries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


class DashboardRepository:
    """Branch-scoped dashboard reads.

    This repository intentionally avoids writes. Dashboard data is derived from
    module-owned tables and scoped by the validated request context.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_branch_name(self, tenant_id: UUID, branch_id: UUID | None) -> str | None:
        if branch_id is None:
            return None
        return self.session.execute(
            text(
                """
                SELECT display_name
                FROM sms_branches
                WHERE tenant_id = :tenant_id
                  AND id = :branch_id
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).scalar_one_or_none()

    def is_branch_in_tenant(self, tenant_id: UUID, branch_id: UUID) -> bool:
        return self.session.execute(
            text(
                """
                SELECT 1
                FROM sms_branches
                WHERE tenant_id = :tenant_id
                  AND id = :branch_id
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).first() is not None

    def get_branch_summaries(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                WITH active_students AS (
                    SELECT e.branch_id, count(DISTINCT s.id) AS cnt
                    FROM sms_enrollments e
                    JOIN sms_students s ON s.id = e.student_id AND s.current_status = 'ACTIVE'
                    WHERE e.tenant_id = :tenant_id AND e.is_current = true AND e.status = 'ACTIVE'
                    GROUP BY e.branch_id
                ),
                total_sections AS (
                    SELECT b.branch_id, count(sec.id) AS total_sec
                    FROM sms_batches b
                    JOIN sms_sections sec ON sec.batch_id = b.id AND sec.status = 'ACTIVE'
                    WHERE b.tenant_id = :tenant_id
                    GROUP BY b.branch_id
                ),
                sessions_today AS (
                    SELECT branch_id, count(id) AS sessions_today
                    FROM sms_attendance_sessions
                    WHERE tenant_id = :tenant_id AND attendance_date = CURRENT_DATE
                    GROUP BY branch_id
                ),
                fees AS (
                    SELECT branch_id, sum(outstanding_amount) AS outstanding
                    FROM sms_fee_accounts
                    WHERE tenant_id = :tenant_id AND status <> 'CANCELLED'
                    GROUP BY branch_id
                )
                SELECT 
                    b.id AS branch_id,
                    b.display_name AS branch_name,
                    COALESCE(stu.cnt, 0) AS active_students,
                    COALESCE(att.sessions_today, 0) AS sessions_today,
                    GREATEST(
                        COALESCE(tsec.total_sec, 0) - COALESCE(att.sessions_today, 0),
                        0
                    ) AS sections_without_session,
                    COALESCE(fee.outstanding, 0) AS fee_outstanding
                FROM sms_branches b
                LEFT JOIN active_students stu ON stu.branch_id = b.id
                LEFT JOIN sessions_today att ON att.branch_id = b.id
                LEFT JOIN total_sections tsec ON tsec.branch_id = b.id
                LEFT JOIN fees fee ON fee.branch_id = b.id
                WHERE b.tenant_id = :tenant_id AND b.status = 'ACTIVE'
                ORDER BY b.display_name
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings()
        return [dict(row) for row in rows]

    def get_student_summary(self, tenant_id: UUID, branch_id: UUID | None) -> dict[str, Any]:
        params = {"tenant_id": tenant_id, "branch_id": branch_id}
        row = self.session.execute(
            text(
                """
                WITH scoped_enrollments AS (
                    SELECT
                        e.id,
                        e.student_id,
                        e.branch_id,
                        e.admission_number,
                        e.created_at
                    FROM sms_enrollments e
                    WHERE e.tenant_id = :tenant_id
                      AND e.is_current = true
                      AND e.status = 'ACTIVE'
                      AND (
                          CAST(:branch_id AS UUID) IS NULL
                          OR e.branch_id = CAST(:branch_id AS UUID)
                      )
                ),
                active_students AS (
                    SELECT DISTINCT s.id
                    FROM sms_students s
                    JOIN scoped_enrollments e ON e.student_id = s.id
                    WHERE s.tenant_id = :tenant_id
                      AND s.current_status = 'ACTIVE'
                ),
                missing_guardians AS (
                    SELECT e.student_id
                    FROM scoped_enrollments e
                    LEFT JOIN sms_student_guardian_links sgl
                      ON sgl.tenant_id = :tenant_id
                     AND sgl.student_id = e.student_id
                     AND sgl.status = 'ACTIVE'
                     AND sgl.is_primary = true
                    LEFT JOIN sms_guardians g
                      ON g.tenant_id = :tenant_id
                     AND g.id = sgl.guardian_id
                    WHERE g.id IS NULL
                       OR NULLIF(g.mobile, '') IS NULL
                ),
                missing_fees AS (
                    SELECT e.id
                    FROM scoped_enrollments e
                    LEFT JOIN sms_fee_accounts fa
                      ON fa.tenant_id = :tenant_id
                     AND fa.enrollment_id = e.id
                     AND fa.status <> 'CANCELLED'
                    WHERE fa.id IS NULL
                )
                SELECT
                    (SELECT count(*) FROM active_students) AS active_students,
                    (SELECT count(*) FROM scoped_enrollments) AS current_enrollments,
                    count(*) FILTER (WHERE se.created_at::date = CURRENT_DATE)
                        AS students_created_today,
                    count(*) FILTER (
                        WHERE se.created_at >= date_trunc('week', CURRENT_DATE)::timestamp
                    ) AS students_created_this_week,
                    (SELECT count(*) FROM missing_guardians) AS missing_guardian_contact,
                    (SELECT count(*) FROM missing_fees) AS missing_fee_accounts
                FROM scoped_enrollments se
                """
            ),
            params,
        ).mappings().one()
        return dict(row)

    def get_recent_students(self, tenant_id: UUID, branch_id: UUID | None) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    s.id,
                    COALESCE(s.display_name, s.legal_name) AS student_name,
                    e.admission_number,
                    ap.programme_name,
                    sec.section_name,
                    s.created_at,
                    COALESCE(b.display_name, b.legal_name) AS branch_name
                FROM sms_enrollments e
                JOIN sms_students s
                  ON s.tenant_id = e.tenant_id
                 AND s.id = e.student_id
                LEFT JOIN sms_academic_programmes ap
                  ON ap.tenant_id = e.tenant_id
                 AND ap.id = e.programme_id
                LEFT JOIN sms_sections sec
                  ON sec.tenant_id = e.tenant_id
                 AND sec.id = e.section_id
                LEFT JOIN sms_branches b
                  ON b.tenant_id = e.tenant_id
                 AND b.id = e.branch_id
                WHERE e.tenant_id = :tenant_id
                  AND e.is_current = true
                  AND (CAST(:branch_id AS UUID) IS NULL OR e.branch_id = CAST(:branch_id AS UUID))
                ORDER BY s.created_at DESC
                LIMIT 5
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).mappings()
        return [dict(row) for row in rows]

    def get_fee_summary(self, tenant_id: UUID, branch_id: UUID | None) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                SELECT
                    count(*) AS active_accounts,
                    COALESCE(sum(net_payable_amount), 0) AS net_payable,
                    COALESCE(sum(total_paid_amount), 0) AS paid,
                    COALESCE(sum(outstanding_amount), 0) AS outstanding,
                    count(*) FILTER (WHERE outstanding_amount > 0) AS accounts_with_due
                FROM sms_fee_accounts
                WHERE tenant_id = :tenant_id
                  AND status <> 'CANCELLED'
                  AND (CAST(:branch_id AS UUID) IS NULL OR branch_id = CAST(:branch_id AS UUID))
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).mappings().one()
        payments_today = self.session.execute(
            text(
                """
                SELECT COALESCE(sum(amount), 0)
                FROM sms_fee_ledger_entries
                WHERE tenant_id = :tenant_id
                  AND entry_type = 'PAYMENT'
                  AND status = 'POSTED'
                  AND receipt_date = CURRENT_DATE
                  AND (CAST(:branch_id AS UUID) IS NULL OR branch_id = CAST(:branch_id AS UUID))
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).scalar_one()
        result: dict[str, Any] = dict(row)
        result["payments_today"] = payments_today or Decimal("0")
        return result

    def get_recent_payments(self, tenant_id: UUID, branch_id: UUID | None) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    fle.id,
                    fle.amount,
                    fle.receipt_number,
                    fle.payment_mode,
                    fle.receipt_date,
                    COALESCE(s.display_name, s.legal_name) AS student_name,
                    e.admission_number,
                    COALESCE(b.display_name, b.legal_name) AS branch_name
                FROM sms_fee_ledger_entries fle
                JOIN sms_students s
                  ON s.tenant_id = fle.tenant_id
                 AND s.id = fle.student_id
                JOIN sms_enrollments e
                  ON e.tenant_id = fle.tenant_id
                 AND e.id = fle.enrollment_id
                LEFT JOIN sms_branches b
                  ON b.tenant_id = fle.tenant_id
                 AND b.id = fle.branch_id
                WHERE fle.tenant_id = :tenant_id
                  AND fle.entry_type = 'PAYMENT'
                  AND fle.status = 'POSTED'
                  AND (CAST(:branch_id AS UUID) IS NULL OR fle.branch_id = CAST(:branch_id AS UUID))
                ORDER BY fle.receipt_date DESC NULLS LAST, fle.created_at DESC
                LIMIT 5
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).mappings()
        return [dict(row) for row in rows]

    def get_attendance_summary(
        self,
        tenant_id: UUID,
        branch_id: UUID | None,
        today: date,
    ) -> dict[str, Any]:
        row = self.session.execute(
            text(
                """
                WITH scoped_sections AS (
                    SELECT sec.id
                    FROM sms_sections sec
                    JOIN sms_batches b
                      ON b.tenant_id = sec.tenant_id
                     AND b.id = sec.batch_id
                    WHERE sec.tenant_id = :tenant_id
                      AND sec.status = 'ACTIVE'
                      AND (
                          CAST(:branch_id AS UUID) IS NULL
                          OR b.branch_id = CAST(:branch_id AS UUID)
                      )
                ),
                sessions_today AS (
                    SELECT *
                    FROM sms_attendance_sessions
                    WHERE tenant_id = :tenant_id
                      AND attendance_date = :today
                      AND (CAST(:branch_id AS UUID) IS NULL OR branch_id = CAST(:branch_id AS UUID))
                )
                SELECT
                    (SELECT count(*) FROM sessions_today) AS sessions_today,
                    count(*) FILTER (WHERE status = 'DRAFT') AS draft_sessions,
                    count(*) FILTER (WHERE status = 'SUBMITTED') AS submitted_sessions,
                    count(*) FILTER (WHERE status = 'FINALIZED') AS finalized_sessions,
                    (SELECT count(*) FROM scoped_sections) AS total_sections,
                    GREATEST(
                        (SELECT count(*) FROM scoped_sections)
                        - (SELECT count(*) FROM sessions_today),
                        0
                    ) AS sections_without_session
                FROM sessions_today
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id, "today": today},
        ).mappings().one()
        return dict(row)

    def get_recent_attendance_sessions(
        self,
        tenant_id: UUID,
        branch_id: UUID | None,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    ats.id,
                    ats.attendance_date,
                    ats.status,
                    sec.section_name,
                    b.batch_name,
                    ap.programme_name
                FROM sms_attendance_sessions ats
                LEFT JOIN sms_sections sec ON sec.id = ats.section_id
                LEFT JOIN sms_batches b ON b.id = sec.batch_id
                LEFT JOIN sms_academic_programmes ap ON ap.id = b.programme_id
                WHERE ats.tenant_id = :tenant_id
                  AND (CAST(:branch_id AS UUID) IS NULL OR ats.branch_id = CAST(:branch_id AS UUID))
                ORDER BY ats.attendance_date DESC, ats.created_at DESC
                LIMIT 5
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).mappings()
        return [dict(row) for row in rows]

    def get_import_summary(self, tenant_id: UUID, branch_id: UUID | None) -> dict[str, Any]:
        rows = self.session.execute(
            text(
                """
                SELECT
                    ib.id,
                    ib.module_code,
                    ib.import_type,
                    ib.source_filename,
                    ib.status,
                    ib.summary,
                    ib.created_at,
                    ib.committed_at,
                    COALESCE(COALESCE(b.display_name, b.legal_name), 'Institution') AS branch_name
                FROM sms_import_batches ib
                LEFT JOIN sms_branches b
                  ON b.tenant_id = ib.tenant_id
                 AND b.id = ib.branch_id
                WHERE ib.tenant_id = :tenant_id
                  AND (
                      CAST(:branch_id AS UUID) IS NULL
                      OR ib.branch_id IS NULL
                      OR ib.branch_id = CAST(:branch_id AS UUID)
                  )
                  AND ib.module_code IN ('students', 'fees')
                ORDER BY ib.created_at DESC
                LIMIT 8
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).mappings().all()
        latest = [dict(row) for row in rows]
        return {
            "total_recent_batches": len(latest),
            "pending_batches": sum(
                1 for row in latest if row["status"] in {"UPLOADED", "PREVIEW", "SUBMITTED"}
            ),
            "failed_or_rejected_batches": sum(
                1 for row in latest if row["status"] in {"FAILED", "REJECTED"}
            ),
            "latest_batches": latest[:5],
        }

    def get_exam_summary(self, tenant_id: UUID, branch_id: UUID | None) -> dict[str, Any]:
        params = {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "branch_id_text": str(branch_id) if branch_id is not None else None,
        }
        row = self.session.execute(
            text(
                """
                SELECT
                    count(*) FILTER (WHERE exam_date >= CURRENT_DATE) AS upcoming_exams,
                    count(*) FILTER (WHERE status = 'DRAFT') AS draft_exams,
                    count(*) FILTER (WHERE status = 'RETURNED_FOR_CORRECTION') AS returned_exams
                FROM sms_exams
                WHERE tenant_id = :tenant_id
                  AND (
                    CAST(:branch_id AS UUID) IS NULL
                    OR branch_id = CAST(:branch_id AS UUID)
                    OR scope = 'ALL_BRANCHES'
                    OR (
                        scope = 'SELECTED_BRANCHES'
                        AND jsonb_exists(branch_ids, :branch_id_text)
                    )
                  )
                """
            ),
            params,
        ).mappings().one()
        marks_entry_pending = self.session.execute(
            text(
                """
                SELECT count(*)
                FROM sms_student_exam_records ser
                JOIN sms_exams ex ON ex.id = ser.exam_id
                WHERE ser.tenant_id = :tenant_id
                  AND ser.status IN ('DRAFT', 'RETURNED_FOR_CORRECTION')
                  AND (
                    CAST(:branch_id AS UUID) IS NULL
                    OR ex.branch_id = CAST(:branch_id AS UUID)
                    OR ex.scope = 'ALL_BRANCHES'
                    OR (
                        ex.scope = 'SELECTED_BRANCHES'
                        AND jsonb_exists(ex.branch_ids, :branch_id_text)
                    )
                  )
                """
            ),
            params,
        ).scalar_one()
        result: dict[str, Any] = dict(row)
        result["marks_entry_pending"] = marks_entry_pending
        return result

    def get_latest_exams(self, tenant_id: UUID, branch_id: UUID | None) -> list[dict[str, Any]]:
        params = {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "branch_id_text": str(branch_id) if branch_id is not None else None,
        }
        rows = self.session.execute(
            text(
                """
                SELECT
                    ex.id,
                    ex.name,
                    ex.type,
                    ex.exam_date,
                    ex.status,
                    ap.programme_name,
                    COALESCE(COALESCE(b.display_name, b.legal_name), 'All Branches') AS branch_name
                FROM sms_exams ex
                LEFT JOIN sms_academic_programmes ap ON ap.id = ex.programme_id
                LEFT JOIN sms_branches b ON b.id = ex.branch_id
                WHERE ex.tenant_id = :tenant_id
                  AND (
                    CAST(:branch_id AS UUID) IS NULL
                    OR ex.branch_id = CAST(:branch_id AS UUID)
                    OR ex.scope = 'ALL_BRANCHES'
                    OR (
                        ex.scope = 'SELECTED_BRANCHES'
                        AND jsonb_exists(ex.branch_ids, :branch_id_text)
                    )
                  )
                ORDER BY ex.exam_date DESC, ex.created_at DESC
                LIMIT 5
                """
            ),
            params,
        ).mappings()
        return [dict(row) for row in rows]
