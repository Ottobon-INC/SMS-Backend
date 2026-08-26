# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Examinations API routes."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.modules.examinations.schemas import (
    BranchExemptionRequest,
    ExamCreate,
    ExamDateOverlapCheckRequest,
    ExamDateOverlapCheckResponse,
    ExamRead,
    ExamSubjectRead,
    ReturnForCorrectionRequest,
    StudentExamRecordBulkSaveRequest,
    StudentExamRecordRead,
)
from app.modules.examinations.service import ExaminationsService

from app.core.security.context import RequestContext
from app.core.security.dependencies import require_tenant_scope, require_any_permission

router = APIRouter(prefix="/examinations", tags=["examinations"])


def get_exam_service(db: Session = Depends(get_db_session)) -> ExaminationsService:
    return ExaminationsService(db)


@router.get("", response_model=list[ExamRead])
def list_exams(
    branch_id: UUID | None = Query(None),
    status: str | None = Query(None),
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.view'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> list[ExamRead]:
    target_branch_id = context.branch_id if context.branch_id else branch_id
    return service.list_exams(tenant_id=context.tenant_id, branch_id=target_branch_id, status=status)


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.manage'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:

    try:
        return service.create_exam(tenant_id=context.tenant_id, user_id=context.app_user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create assessment: {exc}") from exc


@router.get("/{exam_id}", response_model=ExamRead)
def get_exam(
    exam_id: UUID,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.view'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:

    exam = service.get_exam(exam_id=exam_id, tenant_id=context.tenant_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/check-overlap", response_model=ExamDateOverlapCheckResponse)
def check_exam_date_overlap(
    payload: ExamDateOverlapCheckRequest,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.manage'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamDateOverlapCheckResponse:

    return service.check_date_overlap(tenant_id=context.tenant_id, payload=payload)


@router.post("/{exam_id}/exempt-branch", response_model=ExamRead)
def exempt_branch(
    exam_id: UUID,
    payload: BranchExemptionRequest,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.manage'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:

    exam = service.exempt_branch(exam_id=exam_id, tenant_id=context.tenant_id, branch_id=payload.branch_id, reason=payload.reason)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/{exam_id}/return", response_model=ExamRead)
def return_exam(
    exam_id: UUID,
    payload: ReturnForCorrectionRequest,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.publish'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:

    exam = service.return_for_correction(exam_id=exam_id, tenant_id=context.tenant_id, reason=payload.reason)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
    return exam


@router.post("/{exam_id}/publish", response_model=ExamRead)
def publish_exam(
    exam_id: UUID,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.publish'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> ExamRead:

    try:
        exam = service.publish_exam(exam_id=exam_id, tenant_id=context.tenant_id, user_id=context.app_user_id, background_tasks=background_tasks)
        if not exam:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found.")
        return exam
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{exam_id}/subjects", response_model=list[ExamSubjectRead])
def get_exam_subjects(
    exam_id: str,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.view'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> list[ExamSubjectRead]:

    try:
        exam_uuid = UUID(exam_id)
    except ValueError:
        return []
    return service.get_exam_subjects(exam_id=exam_uuid, tenant_id=context.tenant_id)


@router.get("/{exam_id}/records", response_model=list[StudentExamRecordRead])
def get_student_exam_records(
    exam_id: str,
    section_id: UUID | None = Query(None),
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.view'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> list[StudentExamRecordRead]:

    try:
        exam_uuid = UUID(exam_id)
    except ValueError:
        return []
    return service.get_student_exam_records(tenant_id=context.tenant_id, exam_id=exam_uuid, section_id=section_id)


@router.post("/{exam_id}/records/bulk", response_model=list[StudentExamRecordRead])
def bulk_save_student_exam_records(
    exam_id: UUID,
    payload: StudentExamRecordBulkSaveRequest,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(require_tenant_scope),
    _: RequestContext = Depends(require_any_permission({'exam.marks_enter'})),
    service: ExaminationsService = Depends(get_exam_service),
) -> list[StudentExamRecordRead]:

    try:
        return service.bulk_save_student_exam_records(
            tenant_id=context.tenant_id,
            exam_id=exam_id,
            user_id=context.app_user_id,
            records=payload.records,
            background_tasks=background_tasks,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to bulk save records: {exc}") from exc
