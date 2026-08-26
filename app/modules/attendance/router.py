"""Attendance module router providing attendance endpoints."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.dependencies import (
    require_any_permission,
    require_branch_scope,
    require_tenant_scope,
)
from app.modules.attendance import repository, schemas, service

router = APIRouter(prefix="/attendance/sessions", tags=["attendance"])
sections_router = APIRouter(prefix="/attendance/sections", tags=["attendance"])
db_dependency = Depends(get_db_session)
tenant_scope_dependency = Depends(require_tenant_scope)
branch_scope_dependency = Depends(require_branch_scope)
attendance_view_dependency = Depends(require_any_permission({"attendance.view"}))
attendance_mark_dependency = Depends(require_any_permission({"attendance.mark"}))
attendance_submit_dependency = Depends(require_any_permission({"attendance.submit"}))
attendance_finalize_dependency = Depends(require_any_permission({"attendance.finalize"}))
attendance_create_dependency = Depends(
    require_any_permission({"attendance.mark", "attendance.submit", "attendance.view"})
)


@router.get("", response_model=list[schemas.AttendanceSessionListItem])
def list_sessions(
    status: str | None = None,
    db: Session = db_dependency,
    context: RequestContext = tenant_scope_dependency,
    _: RequestContext = attendance_view_dependency,
) -> list[schemas.AttendanceSessionListItem]:
    """List attendance sessions for the current branch or tenant."""
    assert context.tenant_id is not None
    return service.list_sessions(
        db=db,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        status_filter=status,
    )

@router.post("", response_model=schemas.AttendanceSessionResponse)
def create_session(
    payload: schemas.AttendanceSessionCreate,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_create_dependency,
) -> schemas.AttendanceSessionResponse:
    """Create a new daily attendance session (or return existing)."""
    assert context.tenant_id is not None
    assert context.branch_id is not None

    # First check if the session already exists
    existing_session = repository.get_session_by_section_and_date(
        db, UUID(payload.sectionId), payload.attendanceDate
    )
    if existing_session:
        return service._build_session_response(db, existing_session)

    # If we are actually creating a new session, the user must have mutation permissions
    if not (
        context.has_permission("attendance.mark")
        or context.has_permission("attendance.submit")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. You can view existing sessions but cannot create new ones.",
        )

    return service.create_daily_session(
        db=db,
        payload=payload,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        user_id=context.app_user_id,
    )


@router.get("/{session_id}", response_model=schemas.AttendanceSessionResponse)
def get_session(
    session_id: UUID,
    db: Session = db_dependency,
    context: RequestContext = tenant_scope_dependency,
    _: RequestContext = attendance_view_dependency,
) -> schemas.AttendanceSessionResponse:
    """Get a specific attendance session with all student records."""
    assert context.tenant_id is not None
    return service.get_session_with_records(
        db=db,
        session_id=session_id,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,  # None for Dean/Institution Admin — service handles it
    )


@router.put("/{session_id}/records", response_model=schemas.AttendanceSessionResponse)
def save_draft(
    session_id: UUID,
    payload: schemas.AttendanceDraftSavePayload,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_mark_dependency,
) -> schemas.AttendanceSessionResponse:
    """Save draft attendance records."""
    assert context.tenant_id is not None
    assert context.branch_id is not None
    return service.save_draft_records(
        db=db,
        session_id=session_id,
        payload=payload,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        user_id=context.app_user_id,
    )


@router.post("/{session_id}/submit", response_model=schemas.AttendanceSessionResponse)
def submit_session(
    session_id: UUID,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_submit_dependency,
) -> schemas.AttendanceSessionResponse:
    """Submit an attendance session for principal review."""
    assert context.tenant_id is not None
    assert context.branch_id is not None
    return service.submit_session(
        db=db,
        session_id=session_id,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        user_id=context.app_user_id,
    )


@router.post("/{session_id}/return", response_model=schemas.AttendanceSessionResponse)
def return_session_for_revision(
    session_id: UUID,
    payload: schemas.ReturnAttendancePayload,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_finalize_dependency,
) -> schemas.AttendanceSessionResponse:
    """Return a submitted attendance session for revision."""
    assert context.tenant_id is not None
    assert context.branch_id is not None
    return service.return_session_for_revision(
        db=db,
        session_id=session_id,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        user_id=context.app_user_id,
        reason=payload.reason,
    )


@router.post("/{session_id}/finalize", response_model=schemas.AttendanceSessionResponse)
def finalize_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_finalize_dependency,
) -> schemas.AttendanceSessionResponse:
    """Finalize a submitted attendance session."""
    assert context.tenant_id is not None
    return service.finalize_session(
        db=db,
        session_id=session_id,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        user_id=context.app_user_id,
        background_tasks=background_tasks,
    )


@sections_router.get("-status", response_model=list[schemas.SectionAttendanceStatusResponse])
def get_sections_attendance_status(
    date: str,
    batchId: UUID,
    db: Session = db_dependency,
    context: RequestContext = branch_scope_dependency,
    _: RequestContext = attendance_view_dependency,
) -> list[schemas.SectionAttendanceStatusResponse]:
    """Get the attendance status for all sections in a batch for a given date."""
    assert context.tenant_id is not None
    assert context.branch_id is not None
    
    from datetime import datetime
    attendance_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    return service.get_sections_attendance_status(
        db=db,
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        batch_id=batchId,
        attendance_date=attendance_date,
    )
