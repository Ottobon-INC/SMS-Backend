# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Examinations service layer for business logic execution."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.examinations.models import Exam, ExamSubject, StudentExamRecord
from app.modules.examinations.repository import ExaminationsRepository
from app.modules.examinations.schemas import (
    ExamCreate,
    ExamDateOverlapCheckRequest,
    ExamDateOverlapCheckResponse,
    StudentExamRecordSave,
)


class ExaminationsService:
    def __init__(self, db: Session):
        self.repo = ExaminationsRepository(db)

    def create_exam(self, tenant_id: UUID, user_id: UUID, payload: ExamCreate) -> Exam:
        exam_data = payload.model_dump(exclude={"exam_subjects"})
        exam_data["tenant_id"] = tenant_id
        exam_data["created_by"] = user_id
        exam_data["status"] = "DRAFT"

        # Handle branch_id logic for scope
        if payload.scope == "SINGLE_BRANCH" and not payload.branch_id:
            raise ValueError("branch_id is required for SINGLE_BRANCH scope assessments.")

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
        return self.repo.list_exams(tenant_id, branch_id, status)

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
        self, exam_id: UUID, tenant_id: UUID, user_id: UUID
    ) -> Exam | None:
        return self.repo.update_exam(
            exam_id,
            tenant_id,
            {
                "status": "PUBLISHED",
                "published_at": datetime.now(),
                "published_by": user_id,
                "updated_at": datetime.now(),
            },
        )

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
    ) -> list[StudentExamRecord]:
        saved_records = []
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
        return saved_records
