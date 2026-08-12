"""Examinations API routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.modules.examinations.schemas import (
    ExamCreate,
    ExamDateOverlapCheckRequest,
    ExamDateOverlapCheckResponse,
    ExamRead,
    ExamSubjectRead,
    BranchExemptionRequest,
    ReturnForCorrectionRequest,
    StudentExamRecordBulkSaveRequest,
    StudentExamRecordRead,
)
from app.modules.examinations.service import ExaminationsService

router = APIRouter(prefix="/examinations", tags=["examinations"])


def get_exam_service(db: Session = Depends(get_db_session)) -> ExaminationsService:
    return ExaminationsService(db)


# Default tenant & user fallback for dev
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=List[ExamRead])
def list_exams(
    branch_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> List[ExamRead]:
    return service.list_exams(tenant_id=tenant_id, branch_id=branch_id, status=status)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    user_id: UUID = Query(DEFAULT_USER_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:
    try:
        return service.create_exam(tenant_id=tenant_id, user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{exam_id}", response_model=ExamRead)
def get_exam(
    exam_id: UUID,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:
    exam = service.get_exam(exam_id=exam_id, tenant_id=tenant_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/check-overlap", response_model=ExamDateOverlapCheckResponse)
def check_exam_date_overlap(
    payload: ExamDateOverlapCheckRequest,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamDateOverlapCheckResponse:
    return service.check_date_overlap(tenant_id=tenant_id, payload=payload)


@router.post("/{exam_id}/exempt-branch", response_model=ExamRead)
def exempt_branch(
    exam_id: UUID,
    payload: BranchExemptionRequest,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:
    exam = service.exempt_branch(exam_id=exam_id, tenant_id=tenant_id, branch_id=payload.branch_id, reason=payload.reason)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/{exam_id}/return", response_model=ExamRead)
def return_exam(
    exam_id: UUID,
    payload: ReturnForCorrectionRequest,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:
    exam = service.return_for_correction(exam_id=exam_id, tenant_id=tenant_id, reason=payload.reason)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/{exam_id}/publish", response_model=ExamRead)
def publish_exam(
    exam_id: UUID,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    user_id: UUID = Query(DEFAULT_USER_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:
    exam = service.publish_exam(exam_id=exam_id, tenant_id=tenant_id, user_id=user_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.get("/{exam_id}/subjects", response_model=List[ExamSubjectRead])
def get_exam_subjects(
    exam_id: UUID,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> List[ExamSubjectRead]:
    return service.get_exam_subjects(exam_id=exam_id, tenant_id=tenant_id)


@router.get("/{exam_id}/records", response_model=List[StudentExamRecordRead])
def get_student_exam_records(
    exam_id: UUID,
    section_id: Optional[UUID] = Query(None),
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> List[StudentExamRecordRead]:
    return service.get_student_exam_records(tenant_id=tenant_id, exam_id=exam_id, section_id=section_id)


@router.post("/{exam_id}/records/bulk", response_model=List[StudentExamRecordRead])
def bulk_save_student_exam_records(
    exam_id: UUID,
    payload: StudentExamRecordBulkSaveRequest,
    tenant_id: UUID = Query(DEFAULT_TENANT_ID),
    user_id: UUID = Query(DEFAULT_USER_ID),
    service: ExaminationsService = Depends(get_exam_service),
) -> List[StudentExamRecordRead]:
    return service.bulk_save_student_exam_records(
        tenant_id=tenant_id,
        exam_id=exam_id,
        user_id=user_id,
        records=payload.records,
    )
