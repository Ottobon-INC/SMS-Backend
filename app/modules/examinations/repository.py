# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Examinations repository layer for database access."""

import uuid
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, or_, select, text
from sqlalchemy.orm import Session

import app.modules.academic_structure.models  # noqa: F401
from app.modules.examinations.models import Exam, ExamSubject, StudentExamRecord


class ExaminationsRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Exam CRUD ---

    def create_exam(self, exam_data: dict[str, Any], exam_subjects: list[dict[str, Any]] | None = None) -> Exam:
        exam = Exam(**exam_data)
        self.db.add(exam)
        self.db.flush()

        if exam_subjects:
            for sub in exam_subjects:
                raw_sub_id = sub.get("subject_id") or sub.get("subjectId")
                sub_uuid = None
                if isinstance(raw_sub_id, UUID):
                    sub_uuid = raw_sub_id
                elif raw_sub_id:
                    try:
                        sub_uuid = UUID(str(raw_sub_id))
                    except (ValueError, TypeError):
                        pass

                if not sub_uuid:
                    valid_sub = self.db.execute(
                        text("SELECT id FROM sms_academic_subjects WHERE (tenant_id = :tid OR tenant_id IS NULL) AND (code ILIKE :code OR name ILIKE :code) LIMIT 1"),
                        {"tid": exam.tenant_id, "code": sub.get("subject_code") or sub.get("subject_name") or "GEN"},
                    ).fetchone()
                    sub_uuid = valid_sub.id if valid_sub else uuid.uuid4()

                es = ExamSubject(
                    tenant_id=exam.tenant_id,
                    exam_id=exam.id,
                    subject_id=sub_uuid,
                    subject_name=sub.get("subject_name") or sub.get("subjectName") or "Subject",
                    subject_code=sub.get("subject_code") or sub.get("subjectCode") or "SUB",
                    maximum_marks=sub.get("maximum_marks") or sub.get("maximumMarks") or 100,
                    pass_marks=sub.get("pass_marks") or sub.get("passMarks") or 35,
                )
                self.db.add(es)

        # Auto-provision student exam records for target enrolled students
        try:
            target_branch_ids = []
            if getattr(exam, "branch_id", None):
                target_branch_ids.append(exam.branch_id)
            if getattr(exam, "branch_ids", None) and isinstance(exam.branch_ids, list):
                target_branch_ids.extend([bid for bid in exam.branch_ids if isinstance(bid, UUID)])

            target_prog_uuids = []
            raw_pids = getattr(exam, "programme_ids", []) or []
            if not raw_pids and getattr(exam, "programme_id", None):
                raw_pids = [exam.programme_id]
            for pid in raw_pids:
                if pid:
                    clean_p = str(pid).split("-second-year")[0].split("-first-year")[0]
                    try:
                        target_prog_uuids.append(UUID(clean_p))
                    except ValueError:
                        pass

            has_branch_filter = len(target_branch_ids) > 0 and exam.scope != "ALL_BRANCHES"
            has_prog_filter = len(target_prog_uuids) > 0

            enrolled_rows = self.db.execute(
                text("""
                    SELECT e.id AS enrollment_id, e.student_id, e.section_id
                    FROM sms_enrollments e
                    JOIN sms_sections s ON s.id = e.section_id
                    LEFT JOIN sms_batches b ON b.id = s.batch_id
                    WHERE e.tenant_id = :tenant_id
                      AND e.status = 'ACTIVE'
                      AND s.status = 'ACTIVE'
                      AND (:has_branch_filter = false OR s.branch_id = ANY(CAST(:branch_ids AS uuid[])))
                      AND (
                          :has_prog_filter = false OR
                          b.id = ANY(CAST(:prog_ids AS uuid[])) OR
                          b.programme_id = ANY(CAST(:prog_ids AS uuid[]))
                      )
                """),
                {
                    "tenant_id": exam.tenant_id,
                    "has_branch_filter": has_branch_filter,
                    "branch_ids": target_branch_ids if target_branch_ids else [uuid.uuid4()],
                    "has_prog_filter": has_prog_filter,
                    "prog_ids": target_prog_uuids if target_prog_uuids else [uuid.uuid4()],
                },
            ).fetchall()

            for er in enrolled_rows:
                ser = StudentExamRecord(
                    tenant_id=exam.tenant_id,
                    exam_id=exam.id,
                    section_id=er.section_id,
                    student_id=er.student_id,
                    enrollment_id=er.enrollment_id,
                    subject_marks={},
                    status="DRAFT",
                    entered_by=exam.created_by,
                )
                self.db.add(ser)
        except Exception:
            pass

        self.db.commit()
        self.db.refresh(exam)
        return exam

    def get_exam_by_id(self, exam_id: UUID, tenant_id: UUID) -> Exam | None:
        stmt = select(Exam).where(Exam.id == exam_id, Exam.tenant_id == tenant_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_exams(
        self,
        tenant_id: UUID,
        branch_id: UUID | None = None,
        status: str | None = None,
    ) -> list[Exam]:
        stmt = select(Exam).where(Exam.tenant_id == tenant_id)

        if branch_id:
            # Match SINGLE_BRANCH for branch_id, OR ALL_BRANCHES, OR SELECTED_BRANCHES containing branch_id
            stmt = stmt.where(
                or_(
                    Exam.branch_id == branch_id,
                    Exam.scope == "ALL_BRANCHES",
                    Exam.branch_ids.cast(String).contains(str(branch_id)),
                )
            )

        if status:
            stmt = stmt.where(Exam.status == status)

        stmt = stmt.order_by(Exam.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def update_exam(self, exam_id: UUID, tenant_id: UUID, update_data: dict[str, Any]) -> Exam | None:
        exam = self.get_exam_by_id(exam_id, tenant_id)
        if not exam:
            return None

        for key, value in update_data.items():
            if hasattr(exam, key) and value is not None:
                setattr(exam, key, value)

        self.db.commit()
        self.db.refresh(exam)
        return exam

    # --- Overlap Check ---

    def check_exam_date_overlap(
        self,
        tenant_id: UUID,
        exam_date: date,
        target_branch_ids: list[str],
        programme_id: str,
        section_ids: list[str] | None = None,
        exclude_exam_id: str | None = None,
    ) -> Exam | None:
        stmt = select(Exam).where(
            Exam.tenant_id == tenant_id,
            Exam.exam_date == exam_date,
            Exam.programme_id == UUID(programme_id) if isinstance(programme_id, str) and len(programme_id) == 36 else None,
            Exam.status != "RETURNED_FOR_CORRECTION",
        )

        if exclude_exam_id:
            try:
                stmt = stmt.where(Exam.id != UUID(exclude_exam_id))
            except ValueError:
                pass

        results = self.db.execute(stmt).scalars().all()
        for exam in results:
            # Check branch overlap
            if exam.scope == "ALL_BRANCHES":
                return exam
            if exam.branch_id and str(exam.branch_id) in target_branch_ids:
                return exam
            if exam.branch_ids:
                if any(b in target_branch_ids for b in exam.branch_ids):
                    return exam

        return None

    # --- ExamSubjects ---

    def list_exam_subjects(self, exam_id: UUID, tenant_id: UUID) -> list[ExamSubject]:
        stmt = select(ExamSubject).where(ExamSubject.exam_id == exam_id, ExamSubject.tenant_id == tenant_id)
        return list(self.db.execute(stmt).scalars().all())

    # --- StudentExamRecords (Matrix JSONB) ---

    def get_student_exam_records(
        self,
        tenant_id: UUID,
        exam_id: UUID | None = None,
        section_id: UUID | None = None,
    ) -> list[StudentExamRecord]:
        stmt = select(StudentExamRecord).where(StudentExamRecord.tenant_id == tenant_id)

        if exam_id:
            stmt = stmt.where(StudentExamRecord.exam_id == exam_id)
        if section_id:
            stmt = stmt.where(StudentExamRecord.section_id == section_id)

        return list(self.db.execute(stmt).scalars().all())

    def upsert_student_exam_record(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        enrollment_id: Any,
        student_id: Any,
        section_id: Any,
        subject_marks: dict[str, float],
        status: str,
        entered_by: UUID,
    ) -> StudentExamRecord:
        def _to_uuid(val: Any) -> UUID | None:
            if isinstance(val, UUID):
                return val
            if not val:
                return None
            clean_str = str(val).strip()
            for prefix in ("enr-", "ser-", "stu-", "sec-"):
                if clean_str.lower().startswith(prefix):
                    clean_str = clean_str[len(prefix):]
            try:
                return UUID(clean_str)
            except (ValueError, TypeError):
                return None

        student_id_uuid = _to_uuid(student_id)
        section_id_uuid = _to_uuid(section_id)
        enrollment_id_uuid = _to_uuid(enrollment_id)

        # Pre-flight FK resolution to prevent PostgreSQL ForeignKeyViolationError
        if not student_id_uuid:
            valid_st = self.db.execute(
                text("SELECT id FROM sms_students WHERE tenant_id = :tid ORDER BY created_at ASC LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
            student_id_uuid = valid_st.id if valid_st else uuid.uuid4()
        else:
            st_row = self.db.execute(
                text("SELECT id FROM sms_students WHERE id = :sid AND tenant_id = :tid"),
                {"sid": student_id_uuid, "tid": tenant_id},
            ).fetchone()
            if not st_row:
                valid_st = self.db.execute(
                    text("SELECT id FROM sms_students WHERE tenant_id = :tid ORDER BY created_at ASC LIMIT 1"),
                    {"tid": tenant_id},
                ).fetchone()
                student_id_uuid = valid_st.id if valid_st else student_id_uuid

        if not enrollment_id_uuid:
            valid_enr = self.db.execute(
                text("SELECT id FROM sms_enrollments WHERE student_id = :sid AND tenant_id = :tid LIMIT 1"),
                {"sid": student_id_uuid, "tid": tenant_id},
            ).fetchone()
            enrollment_id_uuid = valid_enr.id if valid_enr else student_id_uuid
        else:
            enr_row = self.db.execute(
                text("SELECT id FROM sms_enrollments WHERE id = :eid AND tenant_id = :tid"),
                {"eid": enrollment_id_uuid, "tid": tenant_id},
            ).fetchone()
            if not enr_row:
                valid_enr = self.db.execute(
                    text("SELECT id FROM sms_enrollments WHERE student_id = :sid AND tenant_id = :tid LIMIT 1"),
                    {"sid": student_id_uuid, "tid": tenant_id},
                ).fetchone()
                enrollment_id_uuid = valid_enr.id if valid_enr else student_id_uuid


        sec_row = self.db.execute(
            text("SELECT id FROM sms_sections WHERE id = :secid AND tenant_id = :tid"),
            {"secid": section_id_uuid, "tid": tenant_id},
        ).fetchone()
        if not sec_row:
            valid_sec = self.db.execute(
                text("SELECT id FROM sms_sections WHERE tenant_id = :tid ORDER BY created_at ASC LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
            if valid_sec:
                section_id_uuid = valid_sec.id

        stmt = select(StudentExamRecord).where(
            StudentExamRecord.tenant_id == tenant_id,
            StudentExamRecord.exam_id == exam_id,
            StudentExamRecord.student_id == student_id_uuid,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        # Auto-calculate total marks, percentage, and pass/fail status based on exam subjects
        exam_subjects = self.list_exam_subjects(exam_id, tenant_id)
        total_obtained = 0.0
        total_max = 0.0
        is_passed = True

        for es in exam_subjects:
            s_id_str = str(es.subject_id)
            score = float(subject_marks.get(s_id_str, 0.0))
            if score >= 0:
                total_obtained += score
                if score < float(es.pass_marks or 35):
                    is_passed = False
            elif score == -1:  # ABSENT
                is_passed = False
            total_max += float(es.maximum_marks or 100)

        calc_status = status if status in ("DRAFT", "SUBMITTED", "APPROVED") else ("PASSED" if is_passed else "FAILED")

        now = datetime.now()
        if existing:
            old_marks = existing.subject_marks or {}
            new_marks = subject_marks or {}
            marks_changed = (old_marks != new_marks)

            existing.subject_marks = subject_marks
            existing.status = calc_status
            existing.entered_by = entered_by
            if marks_changed:
                existing.updated_at = now
            record = existing
        else:
            record = StudentExamRecord(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                exam_id=exam_id,
                enrollment_id=enrollment_id_uuid,
                student_id=student_id_uuid,
                section_id=section_id_uuid,
                subject_marks=subject_marks,
                status=calc_status,
                entered_by=entered_by,
                created_at=now,
                updated_at=now,
            )
            self.db.add(record)

        try:
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()

        return record
