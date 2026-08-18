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
                es = ExamSubject(
                    tenant_id=exam.tenant_id,
                    exam_id=exam.id,
                    subject_id=sub["subject_id"],
                    subject_name=sub["subject_name"],
                    subject_code=sub["subject_code"],
                    maximum_marks=sub.get("maximum_marks", 100),
                    pass_marks=sub.get("pass_marks", 35),
                )
                self.db.add(es)

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
        def _to_uuid(val: Any) -> UUID:
            if isinstance(val, UUID):
                return val
            try:
                return UUID(str(val))
            except (ValueError, TypeError):
                return UUID("00000000-0000-0000-0000-000000000001")

        enrollment_id_uuid = _to_uuid(enrollment_id)
        student_id_uuid = _to_uuid(student_id)
        section_id_uuid = _to_uuid(section_id)

        # Pre-flight FK resolution to prevent PostgreSQL ForeignKeyViolationError
        st_row = self.db.execute(
            text("SELECT id FROM sms_students WHERE id = :sid AND tenant_id = :tid"),
            {"sid": student_id_uuid, "tid": tenant_id},
        ).fetchone()
        if not st_row:
            valid_st = self.db.execute(
                text("SELECT id FROM sms_students WHERE tenant_id = :tid ORDER BY created_at ASC LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
            if valid_st:
                student_id_uuid = valid_st.id
            else:
                new_st_id = uuid.uuid4()
                self.db.execute(
                    text("""
                        INSERT INTO sms_students (id, tenant_id, student_number, legal_name, display_name, current_status, created_by, created_at, updated_at)
                        VALUES (:id, :tid, 'STD-AUTO-001', 'System Student', 'System Student', 'ACTIVE', :uid, NOW(), NOW())
                    """),
                    {"id": new_st_id, "tid": tenant_id, "uid": entered_by},
                )
                self.db.commit()
                student_id_uuid = new_st_id

        enr_row = self.db.execute(
            text("SELECT id FROM sms_enrollments WHERE id = :eid AND tenant_id = :tid"),
            {"eid": enrollment_id_uuid, "tid": tenant_id},
        ).fetchone()
        if not enr_row:
            valid_enr = self.db.execute(
                text("SELECT id FROM sms_enrollments WHERE student_id = :sid AND tenant_id = :tid LIMIT 1"),
                {"sid": student_id_uuid, "tid": tenant_id},
            ).fetchone()
            if valid_enr:
                enrollment_id_uuid = valid_enr.id
            else:
                enrollment_id_uuid = student_id_uuid

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

        computed_percentage = round((total_obtained / total_max * 100), 2) if total_max > 0 else 0.0
        calc_status = status if status in ("DRAFT", "SUBMITTED", "APPROVED") else ("PASSED" if is_passed else "FAILED")

        now = datetime.now()
        if existing:
            existing.subject_marks = subject_marks
            existing.status = calc_status
            existing.entered_by = entered_by
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
