# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Examinations service layer for business logic execution."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.examinations.models import Exam, ExamSubject, StudentExamRecord
from app.modules.examinations.repository import ExaminationsRepository
from app.modules.examinations.schemas import (
    ExamCreate,
    ExamDateOverlapCheckRequest,
    ExamDateOverlapCheckResponse,
    StudentExamRecordSave,
)
from app.modules.notifications.service import WhatsAppNotificationService


class ExaminationsService:
    def __init__(self, db: Session):
        self.repo = ExaminationsRepository(db)
        self.notif_service = WhatsAppNotificationService(db)


    def create_exam(self, tenant_id: UUID, user_id: UUID, payload: ExamCreate) -> Exam:
        exam_data = payload.model_dump(exclude={"exam_subjects"})
        exam_data["tenant_id"] = tenant_id
        exam_data["created_by"] = user_id
        exam_data["status"] = "DRAFT"

        # Handle branch_id logic for scope
        if payload.scope == "SINGLE_BRANCH" and not payload.branch_id:
            raise ValueError("branch_id is required for SINGLE_BRANCH scope assessments.")

        # Clean programme_id and programme_ids to valid UUIDs
        if exam_data.get("programme_id"):
            clean_p = str(exam_data["programme_id"]).split("-second-year")[0].split("-first-year")[0]
            try:
                exam_data["programme_id"] = UUID(clean_p)
            except (ValueError, TypeError):
                exam_data["programme_id"] = None

        if exam_data.get("programme_ids") and isinstance(exam_data["programme_ids"], list):
            clean_pids = []
            for pid in exam_data["programme_ids"]:
                if pid:
                    clean_p = str(pid).split("-second-year")[0].split("-first-year")[0]
                    try:
                        clean_pids.append(str(UUID(clean_p)))
                    except (ValueError, TypeError):
                        pass
            exam_data["programme_ids"] = clean_pids

        # FK Resolution 1: Resolve valid sms_academic_programmes.id for programme_id
        prog_fk_valid = False
        if exam_data.get("programme_id"):
            # Check if it directly matches an academic programme
            p_match = self.repo.db.execute(
                text("SELECT id FROM sms_academic_programmes WHERE id = :pid LIMIT 1"),
                {"pid": exam_data["programme_id"]},
            ).fetchone()
            if p_match:
                prog_fk_valid = True
            else:
                # Check if it matches a batch_id and resolve to its programme_id
                b_match = self.repo.db.execute(
                    text("SELECT programme_id FROM sms_batches WHERE id = :bid LIMIT 1"),
                    {"bid": exam_data["programme_id"]},
                ).fetchone()
                if b_match and b_match.programme_id:
                    exam_data["programme_id"] = b_match.programme_id
                    prog_fk_valid = True

        if not prog_fk_valid:
            valid_p = self.repo.db.execute(
                text("SELECT id FROM sms_academic_programmes WHERE tenant_id = :tid AND status = 'ACTIVE' LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
            if valid_p:
                exam_data["programme_id"] = valid_p.id

        # FK Resolution 2: Resolve valid sms_academic_years.id for academic_year_id
        ay_fk_valid = False
        if exam_data.get("academic_year_id"):
            try:
                ay_uuid = UUID(str(exam_data["academic_year_id"]))
                ay_match = self.repo.db.execute(
                    text("SELECT id FROM sms_academic_years WHERE id = :ayid LIMIT 1"),
                    {"ayid": ay_uuid},
                ).fetchone()
                if ay_match:
                    exam_data["academic_year_id"] = ay_match.id
                    ay_fk_valid = True
            except (ValueError, TypeError):
                pass

        if not ay_fk_valid:
            valid_ay = self.repo.db.execute(
                text("SELECT id FROM sms_academic_years WHERE tenant_id = :tid ORDER BY is_current DESC, created_at DESC LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
            if valid_ay:
                exam_data["academic_year_id"] = valid_ay.id

        exam_subjects = [es.model_dump() for es in payload.exam_subjects] if payload.exam_subjects else None
        return self.repo.create_exam(exam_data, exam_subjects)

    def get_exam(self, exam_id: UUID, tenant_id: UUID) -> Exam | None:
        return self.repo.get_exam_by_id(exam_id, tenant_id)

    def list_exams(
        self,
        tenant_id: UUID,
        branch_id: UUID | None = None,
        status: str | None = None,
    ) -> list[Exam]:
        exams = self.repo.list_exams(tenant_id, branch_id, status)

        for exam in exams:
            if exam.status == "DRAFT":
                target_branch_ids = []
                if getattr(exam, "branch_id", None):
                    target_branch_ids.append(str(exam.branch_id))
                if getattr(exam, "branch_ids", None) and isinstance(exam.branch_ids, list):
                    target_branch_ids.extend([str(bid) for bid in exam.branch_ids if bid])

                target_prog_ids = []
                if getattr(exam, "programme_ids", None) and isinstance(exam.programme_ids, list):
                    for pid in exam.programme_ids:
                        if pid:
                            raw_p = str(pid).split("-second-year")[0].split("-first-year")[0]
                            target_prog_ids.append(raw_p)
                elif getattr(exam, "programme_id", None):
                    raw_p = str(exam.programme_id).split("-second-year")[0].split("-first-year")[0]
                    target_prog_ids.append(raw_p)

                stream_codes = []
                if target_prog_ids:
                    progs = self.repo.db.execute(
                        text("SELECT programme_code, stream_code FROM sms_academic_programmes WHERE id::text = ANY(CAST(:p_ids AS text[]))"),
                        {"p_ids": target_prog_ids},
                    ).fetchall()
                    for pr in progs:
                        if pr.stream_code:
                            stream_codes.append(pr.stream_code.upper())
                        if pr.programme_code:
                            stream_codes.append(pr.programme_code.upper())

                excluded_branch_ids = [str(bid) for bid in (getattr(exam, "excluded_branch_ids", []) or []) if bid]
                if getattr(exam, "exemption_reasons", None) and isinstance(exam.exemption_reasons, dict):
                    for ex_bid in exam.exemption_reasons.keys():
                        if ex_bid and str(ex_bid) not in excluded_branch_ids:
                            excluded_branch_ids.append(str(ex_bid))

                has_branch_filter = len(target_branch_ids) > 0
                has_prog_filter = len(target_prog_ids) > 0
                has_stream_filter = len(stream_codes) > 0
                has_excluded_filter = len(excluded_branch_ids) > 0

                target_sections = self.repo.db.execute(
                    text("""
                        SELECT s.id,
                               COALESCE(COUNT(DISTINCT e.id), 0) AS student_count,
                               COALESCE(COUNT(DISTINCT CASE WHEN r.id IS NOT NULL AND r.status IN ('SUBMITTED', 'PUBLISHED', 'EXEMPTED') THEN r.student_id END), 0) AS submitted_count
                        FROM sms_sections s
                        LEFT JOIN sms_batches b ON b.id = s.batch_id
                        JOIN sms_enrollments e ON e.section_id = s.id AND e.status = 'ACTIVE'
                        LEFT JOIN sms_student_exam_records r ON r.section_id = s.id AND r.exam_id = :exam_id
                        WHERE s.tenant_id = :tenant_id
                          AND s.status = 'ACTIVE'
                          AND (:has_branch_filter = false OR s.branch_id::text = ANY(CAST(:branch_ids AS text[])))
                          AND (:has_excluded_filter = false OR s.branch_id::text NOT IN (SELECT unnest(CAST(:excluded_branch_ids AS text[]))))
                          AND (
                              :has_prog_filter = false OR
                              (b.programme_id::text = ANY(CAST(:prog_ids AS text[]))) OR
                              (:has_stream_filter = true AND (EXISTS (SELECT 1 FROM unnest(CAST(:stream_codes AS text[])) code WHERE code <> '' AND (s.section_name ILIKE code || '-%' OR s.section_name ILIKE code || '%'))))
                          )
                        GROUP BY s.id
                        HAVING COUNT(DISTINCT e.id) > 0
                    """),
                    {
                        "tenant_id": tenant_id,
                        "exam_id": exam.id,
                        "has_branch_filter": has_branch_filter,
                        "branch_ids": target_branch_ids if target_branch_ids else [""],
                        "has_excluded_filter": has_excluded_filter,
                        "excluded_branch_ids": excluded_branch_ids if excluded_branch_ids else [""],
                        "has_prog_filter": has_prog_filter,
                        "prog_ids": target_prog_ids if target_prog_ids else [""],
                        "has_stream_filter": has_stream_filter,
                        "stream_codes": stream_codes if stream_codes else [""],
                    },
                ).fetchall()

                if target_sections and all(sec.submitted_count >= sec.student_count for sec in target_sections if sec.student_count > 0):
                    exam.status = "SUBMITTED"
                    self.repo.db.execute(
                        text("UPDATE sms_exams SET status = 'SUBMITTED', updated_at = NOW() WHERE id = :exam_id AND tenant_id = :tenant_id"),
                        {"exam_id": exam.id, "tenant_id": tenant_id},
                    )
                    self.repo.db.commit()


        return exams

    def check_date_overlap(
        self, tenant_id: UUID, payload: ExamDateOverlapCheckRequest
    ) -> ExamDateOverlapCheckResponse:
        conflict = self.repo.check_exam_date_overlap(
            tenant_id=tenant_id,
            exam_date=payload.exam_date,
            target_branch_ids=payload.target_branch_ids,
            programme_id=payload.programme_id,
            section_ids=payload.section_ids,
            exclude_exam_id=payload.exclude_exam_id,
        )

        if conflict:
            return ExamDateOverlapCheckResponse(
                has_overlap=True,
                conflicting_exam_id=str(conflict.id),
                conflicting_exam_name=conflict.name,
            )

        return ExamDateOverlapCheckResponse(has_overlap=False)

    def exempt_branch(
        self, exam_id: UUID, tenant_id: UUID, branch_id: str, reason: str
    ) -> Exam | None:
        exam = self.repo.get_exam_by_id(exam_id, tenant_id)
        if not exam:
            return None

        excluded = list(exam.excluded_branch_ids or [])
        if branch_id not in excluded:
            excluded.append(branch_id)

        reasons = dict(exam.exemption_reasons or {})
        reasons[branch_id] = reason

        return self.repo.update_exam(
            exam_id,
            tenant_id,
            {
                "excluded_branch_ids": excluded,
                "exemption_reasons": reasons,
                "updated_at": datetime.now(),
            },
        )

    def return_for_correction(
        self, exam_id: UUID, tenant_id: UUID, reason: str
    ) -> Exam | None:
        return self.repo.update_exam(
            exam_id,
            tenant_id,
            {
                "status": "RETURNED_FOR_CORRECTION",
                "return_reason": reason,
                "updated_at": datetime.now(),
            },
        )

    def publish_exam(
        self, exam_id: UUID, tenant_id: UUID, user_id: UUID, background_tasks: Any | None = None
    ) -> Exam | None:
        exam = self.repo.get_exam_by_id(exam_id, tenant_id)
        if not exam:
            raise ValueError("Exam not found.")

        # Check if dispatches are already ongoing
        from app.modules.notifications.repository import NotificationsRepository
        from app.modules.notifications.service import WhatsAppNotificationService
        notif_repo = NotificationsRepository(self.repo.db)
        prog = notif_repo.get_progress(str(exam_id))
        if prog["is_ongoing"]:
            raise ValueError("WhatsApp dispatches are currently in progress for this assessment. Duplicate publishing is locked.")

        target_branch_ids = []
        if getattr(exam, "branch_id", None):
            target_branch_ids.append(str(exam.branch_id))
        if getattr(exam, "branch_ids", None) and isinstance(exam.branch_ids, list):
            target_branch_ids.extend([str(bid) for bid in exam.branch_ids if bid])

        target_prog_ids = []
        if getattr(exam, "programme_ids", None) and isinstance(exam.programme_ids, list):
            target_prog_ids.extend([str(pid) for pid in exam.programme_ids if pid])
        elif getattr(exam, "programme_id", None):
            target_prog_ids.append(str(exam.programme_id))

        stream_codes = []
        if target_prog_ids:
            progs = self.repo.db.execute(
                text("SELECT programme_code, stream_code FROM sms_academic_programmes WHERE id::text = ANY(CAST(:p_ids AS text[]))"),
                {"p_ids": target_prog_ids},
            ).fetchall()
            for pr in progs:
                if pr.stream_code:
                    stream_codes.append(pr.stream_code.upper())
                if pr.programme_code:
                    stream_codes.append(pr.programme_code.upper())

        excluded_branch_ids = [str(bid) for bid in (getattr(exam, "excluded_branch_ids", []) or []) if bid]
        if getattr(exam, "exemption_reasons", None) and isinstance(exam.exemption_reasons, dict):
            for ex_bid in exam.exemption_reasons.keys():
                if ex_bid and str(ex_bid) not in excluded_branch_ids:
                    excluded_branch_ids.append(str(ex_bid))

        has_branch_filter = len(target_branch_ids) > 0
        has_prog_filter = len(target_prog_ids) > 0
        has_stream_filter = len(stream_codes) > 0
        has_excluded_filter = len(excluded_branch_ids) > 0

        target_sections = self.repo.db.execute(
            text("""
                SELECT s.id, s.section_name AS name,
                       COALESCE(COUNT(DISTINCT e.id), 0) AS student_count,
                       COALESCE(COUNT(DISTINCT CASE WHEN r.id IS NOT NULL AND r.status IN ('SUBMITTED', 'PUBLISHED', 'EXEMPTED') THEN r.student_id END), 0) AS submitted_count
                FROM sms_sections s
                LEFT JOIN sms_batches b ON b.id = s.batch_id
                JOIN sms_enrollments e ON e.section_id = s.id AND e.status = 'ACTIVE'
                LEFT JOIN sms_student_exam_records r ON r.section_id = s.id AND r.exam_id = :exam_id
                WHERE s.tenant_id = :tenant_id
                  AND s.status = 'ACTIVE'
                  AND (:has_branch_filter = false OR s.branch_id::text = ANY(CAST(:branch_ids AS text[])))
                  AND (:has_excluded_filter = false OR s.branch_id::text NOT IN (SELECT unnest(CAST(:excluded_branch_ids AS text[]))))
                  AND (
                      :has_prog_filter = false OR
                      (b.programme_id::text = ANY(CAST(:prog_ids AS text[]))) OR
                      (:has_stream_filter = true AND (EXISTS (SELECT 1 FROM unnest(CAST(:stream_codes AS text[])) code WHERE code <> '' AND (s.section_name ILIKE code || '-%' OR s.section_name ILIKE code || '%'))))
                  )
                GROUP BY s.id, s.section_name
                HAVING COUNT(DISTINCT e.id) > 0
            """),
            {
                "tenant_id": tenant_id,
                "exam_id": exam_id,
                "has_branch_filter": has_branch_filter,
                "branch_ids": target_branch_ids if target_branch_ids else [""],
                "has_excluded_filter": has_excluded_filter,
                "excluded_branch_ids": excluded_branch_ids if excluded_branch_ids else [""],
                "has_prog_filter": has_prog_filter,
                "prog_ids": target_prog_ids if target_prog_ids else [""],
                "has_stream_filter": has_stream_filter,
                "stream_codes": stream_codes if stream_codes else [""],
            },
        ).fetchall()

        unsubmitted_sections = []
        for sec in target_sections:
            if sec.student_count > 0 and sec.submitted_count < sec.student_count:
                unsubmitted_sections.append(f"{sec.name} ({sec.submitted_count}/{sec.student_count} submitted)")


        if unsubmitted_sections:
            sec_list = ", ".join(unsubmitted_sections[:3])
            raise ValueError(
                f"Cannot publish assessment: The following active class section(s) have unsubmitted student marks: {sec_list}. All active student sections must complete mark entries and submit to Principal before publishing."
            )

        # Generate & Log WhatsApp Parent Notification Dispatches for all enrolled students
        dispatch_rows = self.repo.db.execute(
            text("""
                SELECT
                    st.id AS student_id,
                    COALESCE(st.display_name, st.legal_name) AS student_name,
                    st.student_number,
                    sec.section_name,
                    ex.name AS exam_name,
                    ex.exam_date,
                    g.full_name AS guardian_name,
                    COALESCE(g.mobile, st.student_mobile, '+91 98765 43210') AS guardian_mobile,
                    r.subject_marks
                FROM sms_student_exam_records r
                JOIN sms_students st ON st.id = r.student_id
                LEFT JOIN sms_sections sec ON sec.id = r.section_id
                JOIN sms_exams ex ON ex.id = r.exam_id
                LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = st.id AND sgl.is_primary = true
                LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id
                WHERE r.tenant_id = :tenant_id AND r.exam_id = :exam_id
                ORDER BY sec.section_name, st.legal_name
            """),
            {"tenant_id": tenant_id, "exam_id": exam_id},
        ).fetchall()

        sub_rows = self.repo.db.execute(
            text("""
                SELECT id, subject_id, subject_name, subject_code, maximum_marks, pass_marks
                FROM sms_exam_subjects
                WHERE exam_id = :exam_id
            """),
            {"exam_id": exam_id},
        ).fetchall()

        sub_map = {}
        for s in sub_rows:
            info = {"name": s.subject_name, "max": s.maximum_marks, "pass": s.pass_marks}
            sub_map[str(s.id)] = info
            sub_map[s.subject_code] = info
            if getattr(s, "subject_id", None):
                sub_map[str(s.subject_id)] = info

        master_subs = self.repo.db.execute(
            text("SELECT id, subject_code, subject_name FROM sms_subjects WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).fetchall()
        for ms in master_subs:
            if str(ms.id) not in sub_map:
                sub_map[str(ms.id)] = {"name": ms.subject_name, "max": 100, "pass": 35}
            if ms.subject_code and ms.subject_code not in sub_map:
                sub_map[ms.subject_code] = {"name": ms.subject_name, "max": 100, "pass": 35}

        print("\n" + "=" * 80)
        print("WHATSAPP PARENT NOTIFICATION DISPATCH (SERVER LOG)")
        print("=" * 80)

        dispatched_count = 0
        for row in dispatch_rows:
            subject_marks = row.subject_marks or {}
            score_details = []
            total_obtained = 0
            total_max = 0
            absent_subs = []
            failed_subs = []
            attempted_count = 0

            for sub_key, score_val in subject_marks.items():
                try:
                    score = float(score_val)
                except (ValueError, TypeError):
                    continue

                sub_info = sub_map.get(str(sub_key)) or sub_map.get(str(sub_key).upper())
                sub_name = sub_info["name"] if sub_info else str(sub_key)
                max_m = sub_info["max"] if sub_info else 100
                pass_m = sub_info["pass"] if sub_info else 35

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
                score_details.append(f"  • {sub_name}: {score:g} / {max_m} (Pass: {pass_m}) -> {'PASSED' if is_pass else 'FAILED'}")

            pct = (total_obtained / total_max * 100) if total_max > 0 else 0

            if absent_subs:
                reasons = ", ".join(absent_subs[:2])
                final_status = f"FAILED (Absent in {len(absent_subs)} subjects)" if len(absent_subs) > 2 else f"FAILED (Absent in {reasons})"
            elif failed_subs:
                reasons = ", ".join(failed_subs[:2])
                final_status = f"FAILED (Failed in {len(failed_subs)} subjects)" if len(failed_subs) > 2 else f"FAILED (Failed in {reasons})"
            else:
                final_status = f"PASSED (Passed All {attempted_count} Subjects)" if attempted_count > 0 else "PASSED"

            msg_block = f"""
To Parent Mobile : {row.guardian_mobile} (Guardian: {row.guardian_name or 'Parent/Guardian'})
Student Name     : {row.student_name} ({row.student_number}) | Section: {row.section_name or 'Default'}
Assessment       : {row.exam_name} (Date: {row.exam_date})
--------------------------------------------------------------------------------
MARK DETAILS:
{chr(10).join(score_details) if score_details else '  (No mark details entered)'}
--------------------------------------------------------------------------------
TOTAL SCORE      : {total_obtained:g} / {total_max:g} ({pct:.1f}%)
FINAL STATUS     : {final_status}
--------------------------------------------------------------------------------"""
            print(msg_block)
            dispatched_count += 1

        print(f"Total WhatsApp Dispatches Logged: {dispatched_count}")
        print("=" * 80 + "\n")

        published_exam = self.repo.update_exam(
            exam_id,
            tenant_id,
            {
                "status": "PUBLISHED",
                "published_at": datetime.now(),
                "published_by": user_id,
                "updated_at": datetime.now(),
            },
        )

        if background_tasks:
            print("[PUBLISH] >>> background_tasks available, triggering WhatsApp notifications...")
            try:
                notif_svc = WhatsAppNotificationService(self.repo.db)
                result = notif_svc.send_exam_published_notifications(
                    exam_id=exam_id,
                    tenant_id=tenant_id,
                    branch_id=exam.branch_id,
                    background_tasks=background_tasks,
                )
                print(f"[PUBLISH] >>> Notification trigger result: {result}")
            except Exception as notif_err:
                print(f"[PUBLISH] !!! Notification service trigger WARNING (non-fatal): {notif_err}")
        else:
            print("[PUBLISH] !!! background_tasks is None/falsy - notifications will NOT be sent!")


        return published_exam

    def get_exam_subjects(self, exam_id: UUID, tenant_id: UUID) -> list[ExamSubject]:
        return self.repo.list_exam_subjects(exam_id, tenant_id)

    def get_student_exam_records(
        self,
        tenant_id: UUID,
        exam_id: UUID | None = None,
        section_id: UUID | None = None,
    ) -> list[StudentExamRecord]:
        return self.repo.get_student_exam_records(tenant_id, exam_id, section_id)

    def bulk_save_student_exam_records(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        user_id: UUID,
        records: list[StudentExamRecordSave],
        background_tasks: Any | None = None,
    ) -> list[StudentExamRecord]:
        saved_records = []
        exam = self.repo.get_exam_by_id(exam_id, tenant_id)
        is_published = (exam and getattr(exam, "status", None) == "PUBLISHED")

        for rec in records:
            r = self.repo.upsert_student_exam_record(
                tenant_id=tenant_id,
                exam_id=exam_id,
                enrollment_id=rec.enrollment_id,
                student_id=rec.student_id,
                section_id=rec.section_id,
                subject_marks=rec.subject_marks,
                status=rec.status or "DRAFT",
                entered_by=user_id,
            )
            saved_records.append(r)

            if is_published and rec.student_id and background_tasks is not None:
                branch_id = getattr(exam, "branch_id", None)
                self.notif_service.send_single_student_correction_notification(
                    exam_id=exam_id,
                    student_id=rec.student_id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    background_tasks=background_tasks,
                )


        # Auto-update exam status to SUBMITTED if all active target sections submit class marks
        if exam and getattr(exam, "status", None) not in ("PUBLISHED", "SUBMITTED"):
            target_prog_ids = []
            if getattr(exam, "programme_ids", None) and isinstance(exam.programme_ids, list):
                target_prog_ids.extend([str(pid) for pid in exam.programme_ids if pid])
            elif getattr(exam, "programme_id", None):
                target_prog_ids.append(str(exam.programme_id))

            stream_codes = []
            if target_prog_ids:
                progs = self.repo.db.execute(
                    text("SELECT programme_code, stream_code FROM sms_academic_programmes WHERE id::text = ANY(CAST(:p_ids AS text[]))"),
                    {"p_ids": target_prog_ids},
                ).fetchall()
                for pr in progs:
                    if pr.stream_code:
                        stream_codes.append(pr.stream_code.upper())
                    if pr.programme_code:
                        stream_codes.append(pr.programme_code.upper())

            excluded_branch_ids = [str(bid) for bid in (getattr(exam, "excluded_branch_ids", []) or []) if bid]
            if getattr(exam, "exemption_reasons", None) and isinstance(exam.exemption_reasons, dict):
                for ex_bid in exam.exemption_reasons.keys():
                    if ex_bid and str(ex_bid) not in excluded_branch_ids:
                        excluded_branch_ids.append(str(ex_bid))

            has_prog_filter = len(target_prog_ids) > 0
            has_stream_filter = len(stream_codes) > 0
            has_excluded_filter = len(excluded_branch_ids) > 0

            unsubmitted = self.repo.db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM sms_sections s
                    LEFT JOIN sms_batches b ON b.id = s.batch_id
                    LEFT JOIN (
                        SELECT section_id, MAX(status) as sec_status
                        FROM sms_student_exam_records
                        WHERE exam_id = :exam_id
                        GROUP BY section_id
                    ) r ON r.section_id = s.id
                    WHERE s.tenant_id = :tenant_id
                      AND s.status = 'ACTIVE'
                      AND EXISTS (SELECT 1 FROM sms_enrollments e WHERE e.section_id = s.id AND e.status = 'ACTIVE')
                      AND (:branch_id IS NULL OR s.branch_id = :branch_id)
                      AND (:has_excluded_filter = false OR s.branch_id::text NOT IN (SELECT unnest(CAST(:excluded_branch_ids AS text[]))))
                      AND (
                          :has_prog_filter = false OR
                          (b.programme_id::text = ANY(CAST(:prog_ids AS text[]))) OR
                          (:has_stream_filter = true AND (EXISTS (SELECT 1 FROM unnest(CAST(:stream_codes AS text[])) code WHERE code <> '' AND (s.section_name ILIKE code || '-%' OR s.section_name ILIKE code || '%'))))
                      )
                      AND (r.sec_status IS NULL OR r.sec_status = 'DRAFT')

                """),
                {
                    "exam_id": exam_id,
                    "tenant_id": tenant_id,
                    "branch_id": getattr(exam, "branch_id", None),
                    "has_excluded_filter": has_excluded_filter,
                    "excluded_branch_ids": excluded_branch_ids if excluded_branch_ids else [""],
                    "has_prog_filter": has_prog_filter,
                    "prog_ids": target_prog_ids if target_prog_ids else [""],
                    "has_stream_filter": has_stream_filter,
                    "stream_codes": stream_codes if stream_codes else [""],
                },
            ).scalar() or 0

            if unsubmitted == 0:
                self.repo.db.execute(
                    text("UPDATE sms_exams SET status = 'SUBMITTED', updated_at = NOW() WHERE id = :exam_id AND tenant_id = :tenant_id"),
                    {"exam_id": exam_id, "tenant_id": tenant_id},
                )
                self.repo.db.commit()


        return saved_records

    def notify_single_student_correction(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        student_id: UUID,
        user_id: UUID,
    ) -> None:
        """Logs a targeted WhatsApp correction notification for ONLY one modified student."""
        query = text("""
            SELECT
                s.legal_name AS student_name,
                s.student_number,
                g.full_name AS guardian_name,
                g.mobile AS guardian_mobile,
                ex.name AS exam_name,
                ex.exam_date,
                sec.section_name,
                r.subject_marks
            FROM sms_student_exam_records r
            JOIN sms_students s ON s.id = r.student_id
            JOIN sms_exams ex ON ex.id = r.exam_id
            LEFT JOIN sms_sections sec ON sec.id = r.section_id
            LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = s.id AND sgl.is_primary = true AND sgl.status = 'ACTIVE'
            LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id
            WHERE r.tenant_id = :tenant_id AND r.exam_id = :exam_id AND r.student_id = :student_id
            LIMIT 1
        """)
        row = self.repo.db.execute(query, {"tenant_id": tenant_id, "exam_id": exam_id, "student_id": student_id}).fetchone()
        if not row or not row.guardian_mobile:
            return

        sub_rows = self.repo.db.execute(
            text("SELECT id, subject_id, subject_name, subject_code, maximum_marks, pass_marks FROM sms_exam_subjects WHERE exam_id = :exam_id"),
            {"exam_id": exam_id},
        ).fetchall()

        sub_map = {}
        for s in sub_rows:
            info = {"name": s.subject_name, "max": s.maximum_marks, "pass": s.pass_marks}
            sub_map[str(s.id)] = info
            sub_map[s.subject_code] = info
            if getattr(s, "subject_id", None):
                sub_map[str(s.subject_id)] = info

        master_subs = self.repo.db.execute(
            text("SELECT id, subject_code, subject_name FROM sms_subjects WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).fetchall()
        for ms in master_subs:
            if str(ms.id) not in sub_map:
                sub_map[str(ms.id)] = {"name": ms.subject_name, "max": 100, "pass": 35}
            if ms.subject_code and ms.subject_code not in sub_map:
                sub_map[ms.subject_code] = {"name": ms.subject_name, "max": 100, "pass": 35}

        subject_marks = row.subject_marks or {}
        score_details = []
        total_obtained = 0
        total_max = 0
        absent_subs = []
        failed_subs = []
        attempted_count = 0

        for sub_key, score_val in subject_marks.items():
            try:
                score = float(score_val)
            except (ValueError, TypeError):
                continue

            sub_info = sub_map.get(str(sub_key)) or sub_map.get(str(sub_key).upper())
            sub_name = sub_info["name"] if sub_info else str(sub_key)
            max_m = sub_info["max"] if sub_info else 100
            pass_m = sub_info["pass"] if sub_info else 35

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
            score_details.append(f"  • {sub_name}: {score:g} / {max_m} (Pass: {pass_m}) -> {'PASSED' if is_pass else 'FAILED'}")

        pct = (total_obtained / total_max * 100) if total_max > 0 else 0

        if absent_subs:
            reasons = ", ".join(absent_subs[:2])
            final_status = f"FAILED (Absent in {len(absent_subs)} subjects)" if len(absent_subs) > 2 else f"FAILED (Absent in {reasons})"
        elif failed_subs:
            reasons = ", ".join(failed_subs[:2])
            final_status = f"FAILED (Failed in {len(failed_subs)} subjects)" if len(failed_subs) > 2 else f"FAILED (Failed in {reasons})"
        else:
            final_status = f"PASSED (Passed All {attempted_count} Subjects)" if attempted_count > 0 else "PASSED"

        print("\n" + "=" * 80)
        print("TARGETED SINGLE-STUDENT WHATSAPP CORRECTION DISPATCH (SERVER LOG)")
        print("=" * 80)
        print(f"To Parent Mobile : {row.guardian_mobile} (Guardian: {row.guardian_name or 'Parent/Guardian'})")
        print(f"Student Name     : {row.student_name} ({row.student_number}) | Section: {row.section_name or 'Default'}")
        print(f"Assessment       : {row.exam_name} (Date: {row.exam_date})")
        print(f"Correction Type  : Single Student Mark Update (Post-Publish)")
        print("-" * 80)
        print("UPDATED MARK DETAILS:")
        print(chr(10).join(score_details) if score_details else "  (No mark details entered)")
        print("-" * 80)
        print(f"UPDATED TOTAL    : {total_obtained:g} / {total_max:g} ({pct:.1f}%)")
        print(f"UPDATED STATUS   : {final_status}")
        print("=" * 80 + "\n")
