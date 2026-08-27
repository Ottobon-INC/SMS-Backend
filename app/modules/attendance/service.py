"""Attendance module service layer."""

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic_structure.models import Batch, Section
from app.modules.academic_structure.constants import programme_display_label
from app.modules.attendance import repository, schemas
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.audit.models import AuditEvent


def _get_section_or_404(db: Session, section_id: UUID, tenant_id: UUID, branch_id: UUID) -> Section:
    section = (
        db.query(Section)
        .filter_by(id=section_id, tenant_id=tenant_id, branch_id=branch_id)
        .first()
    )
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Section not found or access denied.",
        )
    return section


def _get_session_or_404(
    db: Session, session_id: UUID, tenant_id: UUID, branch_id: UUID | None
) -> AttendanceSession:
    session = repository.get_session_by_id(db, session_id)
    if not session or session.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found or access denied.",
        )
    # If caller has branch scope (Office Staff / Principal), also enforce branch match
    if branch_id is not None and session.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found or access denied.",
        )
    return session


def _get_user_name(db: Session, user_id: UUID | None) -> str | None:
    """Resolve a user UUID to the user's full_name. Returns None if not found."""
    if user_id is None:
        return None
    from sqlalchemy import String, column, table

    sms_users = table("sms_users", column("id"), column("full_name", String))
    stmt = select(sms_users.c.full_name).where(sms_users.c.id == user_id)
    row = db.execute(stmt).fetchone()
    return row[0] if row else str(user_id)


def _build_session_response(
    db: Session, session: AttendanceSession
) -> schemas.AttendanceSessionResponse:
    enrollments_data = repository.get_active_enrollments_for_section(db, session.section_id)
    records = repository.get_records_for_session(db, session.id)

    record_map = {r.enrollment_id: r for r in records}

    students = []
    for enrollment, student in enrollments_data:
        record = record_map.get(enrollment.id)
        students.append(
            schemas.AttendanceStudentResponse(
                enrollmentId=str(enrollment.id),
                studentId=str(student.id),
                studentName=student.display_name or student.legal_name,
                admissionNumber=enrollment.admission_number,
                rollNumber=enrollment.roll_number,
                attendanceStatus=record.attendance_status if record else "UNMARKED",
                note=record.note if record else None,
            )
        )

    revision_reason = None
    if session.status == "DRAFT":
        from sqlalchemy import desc
        latest_return_audit = (
            db.query(AuditEvent)
            .filter_by(target_id=session.id, action_key="ATTENDANCE_RETURNED_FOR_REVISION")
            .order_by(desc("created_at"))
            .first()
        )
        if latest_return_audit:
            revision_reason = getattr(latest_return_audit, "reason", None)

    return schemas.AttendanceSessionResponse(
        id=str(session.id),
        tenantId=str(session.tenant_id),
        branchId=str(session.branch_id),
        academicYearId=str(session.academic_year_id),
        batchId=str(session.batch_id),
        sectionId=str(session.section_id),
        attendanceDate=session.attendance_date,
        status=session.status,
        openedBy=_get_user_name(db, session.opened_by) or str(session.opened_by),
        submittedBy=_get_user_name(db, session.submitted_by),
        submittedAt=session.submitted_at,
        finalizedBy=_get_user_name(db, session.finalized_by),
        finalizedAt=session.finalized_at,
        revisionReason=revision_reason,
        students=students,
    )


def create_daily_session(
    db: Session,
    payload: schemas.AttendanceSessionCreate,
    tenant_id: UUID,
    branch_id: UUID,
    user_id: UUID,
) -> schemas.AttendanceSessionResponse:
    """Create a new daily attendance session."""
    if payload.attendanceDate > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot mark attendance for future dates.",
        )

    section_id = UUID(payload.sectionId)
    section = _get_section_or_404(db, section_id, tenant_id, branch_id)

    # get academic_year_id from Batch
    batch = db.query(Batch).filter_by(id=section.batch_id).first()
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch configuration missing",
        )

    existing_session = repository.get_session_by_section_and_date(
        db,
        section_id,
        payload.attendanceDate,
    )
    if existing_session:
        return _build_session_response(db, existing_session)

    new_session = AttendanceSession(
        tenant_id=tenant_id,
        branch_id=branch_id,
        academic_year_id=batch.academic_year_id,
        batch_id=batch.id,
        section_id=section_id,
        attendance_date=payload.attendanceDate,
        status="DRAFT",
        opened_by=user_id,
    )

    created_session = repository.create_session(db, new_session)
    db.commit()
    return _build_session_response(db, created_session)


def get_session_with_records(
    db: Session,
    session_id: UUID,
    tenant_id: UUID,
    branch_id: UUID | None,
) -> schemas.AttendanceSessionResponse:
    """Fetch an attendance session along with all active student enrollments."""
    session = _get_session_or_404(db, session_id, tenant_id, branch_id)
    return _build_session_response(db, session)


def save_draft_records(
    db: Session,
    session_id: UUID,
    payload: schemas.AttendanceDraftSavePayload,
    tenant_id: UUID,
    branch_id: UUID,
    user_id: UUID,
) -> schemas.AttendanceSessionResponse:
    """Save attendance records as a draft."""
    session = _get_session_or_404(db, session_id, tenant_id, branch_id)

    if session.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only save draft records for a DRAFT session.",
        )

    now_ts = datetime.now(UTC)

    for record_data in payload.records:
        if record_data.attendanceStatus == "UNMARKED":
            continue

        record = AttendanceRecord(
            tenant_id=tenant_id,
            branch_id=branch_id,
            session_id=session.id,
            enrollment_id=UUID(record_data.enrollmentId),
            attendance_status=record_data.attendanceStatus,
            note=record_data.note,
            marked_by=user_id,
            marked_at=now_ts,
            updated_at=now_ts,
        )
        repository.upsert_attendance_record(db, record)

    db.commit()
    return _build_session_response(db, session)


def submit_session(
    db: Session,
    session_id: UUID,
    tenant_id: UUID,
    branch_id: UUID,
    user_id: UUID,
) -> schemas.AttendanceSessionResponse:
    """Submit a draft attendance session for review."""
    session = _get_session_or_404(db, session_id, tenant_id, branch_id)

    if session.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only DRAFT sessions can be submitted.",
        )

    # Verify all active enrollments have a record
    enrollments_data = repository.get_active_enrollments_for_section(db, session.section_id)
    records = repository.get_records_for_session(db, session.id)

    record_map = {r.enrollment_id: r for r in records}

    missing_students = []
    for enrollment, student in enrollments_data:
        if enrollment.id not in record_map:
            missing_students.append(student.display_name or student.legal_name)

    if missing_students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit. Missing attendance for {len(missing_students)} students.",
        )

    repository.update_session_status(
        db,
        session.id,
        "SUBMITTED",
        user_id,
        datetime.now(UTC),
    )
    db.commit()
    return _build_session_response(db, session)


def return_session_for_revision(
    db: Session,
    session_id: UUID,
    tenant_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    reason: str | None = None,
) -> schemas.AttendanceSessionResponse:
    """Return a submitted attendance session for revision."""
    session = _get_session_or_404(db, session_id, tenant_id, branch_id)

    if session.status != "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUBMITTED sessions can be returned for revision.",
        )

    # Transition back to DRAFT and clear submission metadata
    repository.update_session_status(
        db,
        session.id,
        "DRAFT",
        user_id,
        datetime.now(UTC),
    )

    # Record an audit event preserving the return action
    audit_event = AuditEvent(
        tenant_id=tenant_id,
        branch_id=branch_id,
        actor_user_id=user_id,
        module_code="attendance",
        action_key="ATTENDANCE_RETURNED_FOR_REVISION",
        target_type="AttendanceSession",
        target_id=session.id,
        outcome="SUCCEEDED",
        reason=reason,
        correlation_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    db.add(audit_event)

    db.commit()
    return _build_session_response(db, session)


def finalize_session(
    db: Session,
    session_id: UUID,
    tenant_id: UUID,
    branch_id: UUID,
    user_id: UUID,
    background_tasks: Any | None = None,
) -> schemas.AttendanceSessionResponse:
    """Finalize a submitted attendance session and trigger WhatsApp absent alerts."""
    session = _get_session_or_404(db, session_id, tenant_id, branch_id)

    if session.status != "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUBMITTED sessions can be finalized.",
        )

    repository.update_session_status(
        db,
        session.id,
        "FINALIZED",
        user_id,
        datetime.now(UTC),
    )
    db.commit()

    if background_tasks:
        try:
            records = repository.get_records_for_session(db, session.id)
            absent_enrollment_ids = [
                r.enrollment_id for r in records if r.attendance_status == "ABSENT"
            ]

            if absent_enrollment_ids:
                from sqlalchemy import text

                from app.modules.notifications.service import WhatsAppNotificationService

                stu_rows = db.execute(
                    text(
                        "SELECT student_id FROM sms_enrollments "
                        "WHERE id::text = ANY(CAST(:e_ids AS text[]))"
                    ),
                    {"e_ids": [str(e) for e in absent_enrollment_ids]},
                ).fetchall()
                absent_student_ids = [r.student_id for r in stu_rows]

                sec_row = db.execute(
                    text("SELECT section_name FROM sms_sections WHERE id = :id"),
                    {"id": session.section_id},
                ).first()
                section_name = sec_row.section_name if sec_row else "Default"

                notif_svc = WhatsAppNotificationService(db)
                notif_svc.send_attendance_absent_notifications(
                    section_id=session.section_id,
                    section_name=section_name,
                    absent_student_ids=absent_student_ids,
                    date_str=str(session.attendance_date),
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    background_tasks=background_tasks,
                )
        except Exception as notif_err:
            print(f"Attendance notification trigger warning: {notif_err}")

    return _build_session_response(db, session)


def list_sessions(
    db: Session,
    tenant_id: UUID,
    branch_id: UUID | None,
    status_filter: str | None = None,
) -> list[schemas.AttendanceSessionListItem]:
    """Retrieve all attendance sessions for a branch or tenant, joined with academic structures."""
    results = repository.get_sessions_list(db, tenant_id, branch_id, status_filter)

    return [
        schemas.AttendanceSessionListItem(
            id=str(session.id),
            tenantId=str(session.tenant_id),
            branchId=str(session.branch_id),
            academicYearId=str(session.academic_year_id),
            batchId=str(session.batch_id),
            sectionId=str(session.section_id),
            sectionName=section.section_name,
            batchName=batch.batch_name,
            programmeName=programme_display_label(
                programme_code=programme.programme_code,
                programme_name=programme.programme_name,
                stream_code=getattr(programme, "stream_code", None),
                coaching_track=getattr(programme, "coaching_track", None),
            ),
            attendanceDate=session.attendance_date,
            status=session.status,
            openedBy=_get_user_name(db, session.opened_by) or str(session.opened_by),
            submittedBy=_get_user_name(db, session.submitted_by),
            submittedAt=session.submitted_at,
            finalizedBy=_get_user_name(db, session.finalized_by),
            finalizedAt=session.finalized_at,
        )
        for session, section, batch, programme in results
    ]


def get_sections_attendance_status(
    db: Session,
    tenant_id: UUID,
    branch_id: UUID,
    batch_id: UUID,
    attendance_date: date,
) -> list[schemas.SectionAttendanceStatusResponse]:
    """Get the attendance status for all sections in a batch for a given date."""
    results = repository.get_sections_attendance_status(
        db, tenant_id, branch_id, batch_id, attendance_date
    )

    response = []
    for section, batch, session in results:
        status = session.status if session else "UNMARKED"
        session_id = str(session.id) if session else None
        response.append(
            schemas.SectionAttendanceStatusResponse(
                sectionId=str(section.id),
                sectionName=section.section_name,
                batchName=batch.batch_name,
                status=status,
                sessionId=session_id,
            )
        )
    return response
