"""Examinations service layer for business logic coordination."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.examinations.repository import ExaminationsRepository
from app.modules.examinations.schemas import (
    ExamCreate,
    ExamDateOverlapCheckRequest,
    ExamDateOverlapCheckResponse,
    ExamRead,
    ExamSubjectRead,
    StudentExamRecordItem,
    StudentExamRecordRead,
)


class ExaminationsService:
    def __init__(self, db: Session):
        self.repository = ExaminationsRepository(db)

    def list_exams(
        self,
        tenant_id: UUID,
        branch_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> List[ExamRead]:
        exams = self.repository.list_exams(tenant_id=tenant_id, branch_id=branch_id, status=status)
        return [ExamRead.model_validate(e) for e in exams]

    def create_exam(
        self,
        tenant_id: UUID,
        user_id: UUID,
        payload: ExamCreate,
    ) -> ExamRead:
        exam_data = {
            "tenant_id": tenant_id,
            "branch_id": payload.branch_id,
            "scope": payload.scope,
            "branch_ids": payload.branch_ids,
            "academic_year_id": payload.academic_year_id,
            "programme_id": payload.programme_id,
            "name": payload.name,
            "type": payload.type,
            "exam_date": payload.exam_date,
            "marks_entry_deadline": payload.marks_entry_deadline,
            "status": "DRAFT",
            "created_by": user_id,
        }

        exam_subjects = None
        if payload.subjects:
            exam_subjects = [sub.model_dump() for sub in payload.subjects]

        exam = self.repository.create_exam(exam_data=exam_data, exam_subjects=exam_subjects)
        return ExamRead.model_validate(exam)

    def get_exam(self, exam_id: UUID, tenant_id: UUID) -> Optional[ExamRead]:
        exam = self.repository.get_exam_by_id(exam_id=exam_id, tenant_id=tenant_id)
        if not exam:
            return None
        return ExamRead.model_validate(exam)

    def check_date_overlap(
        self,
        tenant_id: UUID,
        payload: ExamDateOverlapCheckRequest,
    ) -> ExamDateOverlapCheckResponse:
        overlapping_exam = self.repository.check_exam_date_overlap(
            tenant_id=tenant_id,
            exam_date=payload.exam_date,
            target_branch_ids=payload.target_branch_ids,
            programme_id=payload.programme_id,
            section_ids=payload.section_ids,
            exclude_exam_id=payload.exclude_exam_id,
        )

        if overlapping_exam:
            return ExamDateOverlapCheckResponse(
                has_overlap=True,
                overlapping_exam_id=overlapping_exam.id,
                overlapping_exam_name=overlapping_exam.name,
                message=f"Date overlaps with existing exam '{overlapping_exam.name}'",
            )

        return ExamDateOverlapCheckResponse(has_overlap=False)

    def exempt_branch(
        self,
        exam_id: UUID,
        tenant_id: UUID,
        branch_id: UUID,
        reason: str,
    ) -> Optional[ExamRead]:
        exam = self.repository.get_exam_by_id(exam_id=exam_id, tenant_id=tenant_id)
        if not exam:
            return None

        excluded = exam.excluded_branch_ids or []
        b_str = str(branch_id)
        if b_str not in excluded:
            excluded.append(b_str)

        reasons = exam.exemption_reasons or {}
        reasons[b_str] = reason

        updated = self.repository.update_exam(
            exam_id=exam_id,
            tenant_id=tenant_id,
            update_data={
                "excluded_branch_ids": excluded,
                "exemption_reasons": reasons,
            },
        )
        return ExamRead.model_validate(updated) if updated else None

    def return_for_correction(
        self,
        exam_id: UUID,
        tenant_id: UUID,
        reason: str,
    ) -> Optional[ExamRead]:
        updated = self.repository.update_exam(
            exam_id=exam_id,
            tenant_id=tenant_id,
            update_data={
                "status": "RETURNED_FOR_CORRECTION",
                "return_reason": reason,
            },
        )
        return ExamRead.model_validate(updated) if updated else None

    def publish_exam(
        self,
        exam_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[ExamRead]:
        updated = self.repository.update_exam(
            exam_id=exam_id,
            tenant_id=tenant_id,
            update_data={
                "status": "PUBLISHED",
                "published_at": datetime.now(),
                "published_by": user_id,
            },
        )
        return ExamRead.model_validate(updated) if updated else None

    def get_exam_subjects(self, exam_id: UUID, tenant_id: UUID) -> List[ExamSubjectRead]:
        subjects = self.repository.list_exam_subjects(exam_id=exam_id, tenant_id=tenant_id)
        return [ExamSubjectRead.model_validate(s) for s in subjects]

    def get_student_exam_records(
        self,
        tenant_id: UUID,
        exam_id: Optional[UUID] = None,
        section_id: Optional[UUID] = None,
    ) -> List[StudentExamRecordRead]:
        records = self.repository.get_student_exam_records(
            tenant_id=tenant_id,
            exam_id=exam_id,
            section_id=section_id,
        )
        return [StudentExamRecordRead.model_validate(r) for r in records]

    def bulk_save_student_exam_records(
        self,
        tenant_id: UUID,
        exam_id: UUID,
        user_id: UUID,
        records: List[StudentExamRecordItem],
    ) -> List[StudentExamRecordRead]:
        saved_records = []
        for item in records:
            rec = self.repository.upsert_student_exam_record(
                tenant_id=tenant_id,
                exam_id=exam_id,
                enrollment_id=item.enrollment_id,
                student_id=item.student_id,
                section_id=item.section_id,
                subject_marks=item.subject_marks,
                status=item.status,
                entered_by=user_id,
            )
            saved_records.append(StudentExamRecordRead.model_validate(rec))
        return saved_records
