# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Examinations repository layer for database access."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import String, or_, select
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
        enrollment_id: UUID,
        student_id: UUID,
        section_id: UUID,
        subject_marks: dict[str, float],
        status: str,
        entered_by: UUID,
    ) -> StudentExamRecord:
        stmt = select(StudentExamRecord).where(
            StudentExamRecord.tenant_id == tenant_id,
            StudentExamRecord.exam_id == exam_id,
            StudentExamRecord.student_id == student_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            existing.subject_marks = subject_marks
            existing.status = status
            existing.entered_by = entered_by
            record = existing
        else:
            record = StudentExamRecord(
                tenant_id=tenant_id,
                exam_id=exam_id,
                enrollment_id=enrollment_id,
                student_id=student_id,
                section_id=section_id,
                subject_marks=subject_marks,
                status=status,
                entered_by=entered_by,
            )
            self.db.add(record)

        self.db.commit()
        self.db.refresh(record)
        return record
