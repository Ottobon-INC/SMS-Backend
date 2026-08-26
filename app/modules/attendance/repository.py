"""Attendance repository for database operations."""

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.modules.academic_structure.models import AcademicProgramme, Batch, Section
from app.modules.attendance.models import AttendanceRecord, AttendanceSession
from app.modules.students.models import Enrollment, Student


def get_session_by_id(db: Session, session_id: UUID) -> AttendanceSession | None:
    """Fetch an attendance session by its ID."""
    stmt = select(AttendanceSession).where(AttendanceSession.id == session_id)
    return db.execute(stmt).scalar_one_or_none()


def get_session_by_section_and_date(
    db: Session, section_id: UUID, attendance_date: date
) -> AttendanceSession | None:
    """Fetch an attendance session by section and date."""
    stmt = select(AttendanceSession).where(
        and_(
            AttendanceSession.section_id == section_id,
            AttendanceSession.attendance_date == attendance_date,
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def create_session(db: Session, session: AttendanceSession) -> AttendanceSession:
    """Create a new attendance session."""
    db.add(session)
    db.flush()
    return session


def get_active_enrollments_for_section(db: Session, section_id: UUID) -> Any:
    """Fetch all active enrollments for a given section joined with Student."""
    stmt = (
        select(Enrollment, Student)
        .join(Student, Enrollment.student_id == Student.id)
        .where(
            and_(
                Enrollment.section_id == section_id,
                Enrollment.status == "ACTIVE",
                Enrollment.is_current.is_(True),
            )
        )
        .order_by(Enrollment.roll_number, Student.legal_name)
    )
    return list(db.execute(stmt).all())


def get_records_for_session(db: Session, session_id: UUID) -> list[AttendanceRecord]:
    """Fetch all attendance records for a specific session."""
    stmt = select(AttendanceRecord).where(AttendanceRecord.session_id == session_id)
    return list(db.execute(stmt).scalars().all())


def upsert_attendance_record(db: Session, record: AttendanceRecord) -> AttendanceRecord:
    """Insert or update an attendance record."""
    # We will use simple merge or check-and-update since SQLAlchemy ORM merge works well
    # for UUID PKs, but we don't have PK set for updates.
    # It's better to query existing by session_id and enrollment_id, or let the service handle it.

    existing = db.execute(
        select(AttendanceRecord).where(
            and_(
                AttendanceRecord.session_id == record.session_id,
                AttendanceRecord.enrollment_id == record.enrollment_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.attendance_status = record.attendance_status
        existing.note = record.note
        existing.marked_by = record.marked_by
        existing.marked_at = record.marked_at
        existing.updated_at = record.updated_at
        return existing
    else:
        db.add(record)
        return record


def update_session_status(
    db: Session,
    session_id: UUID,
    status: str,
    user_id: UUID,
    timestamp: Any,
) -> None:
    """Update the status of a session (e.g. SUBMITTED or FINALIZED)."""
    values = {"status": status, "updated_at": timestamp}

    if status == "SUBMITTED":
        values["submitted_by"] = user_id
        values["submitted_at"] = timestamp
    elif status == "FINALIZED":
        values["finalized_by"] = user_id
        values["finalized_at"] = timestamp
    elif status == "DRAFT":
        # Clear submission metadata when returning for revision
        values["submitted_by"] = None
        values["submitted_at"] = None

    stmt = (
        update(AttendanceSession)
        .where(AttendanceSession.id == session_id)
        .values(**values)
    )
    db.execute(stmt)


def get_sessions_list(
    db: Session, tenant_id: UUID, branch_id: UUID | None = None, status: str | None = None
) -> Any:
    """Fetch all attendance sessions for a branch or tenant with academic structure joins."""
    stmt = (
        select(AttendanceSession, Section, Batch, AcademicProgramme)
        .join(Section, AttendanceSession.section_id == Section.id)
        .join(Batch, Section.batch_id == Batch.id)
        .join(AcademicProgramme, Batch.programme_id == AcademicProgramme.id)
        .where(AttendanceSession.tenant_id == tenant_id)
    )
    if branch_id:
        stmt = stmt.where(AttendanceSession.branch_id == branch_id)
    if status:
        stmt = stmt.where(AttendanceSession.status == status)

    stmt = stmt.order_by(AttendanceSession.attendance_date.desc(), Section.section_name)
    return list(db.execute(stmt).all())


def get_sections_attendance_status(
    db: Session,
    tenant_id: UUID,
    branch_id: UUID,
    batch_id: UUID,
    attendance_date: date,
) -> Any:
    """Fetch sections for a given batch with their attendance session status for a specific date."""
    stmt = (
        select(Section, Batch, AttendanceSession)
        .join(Batch, Section.batch_id == Batch.id)
        .outerjoin(
            AttendanceSession,
            and_(
                AttendanceSession.section_id == Section.id,
                AttendanceSession.attendance_date == attendance_date,
            ),
        )
        .where(
            and_(
                Section.tenant_id == tenant_id,
                Section.branch_id == branch_id,
                Section.batch_id == batch_id,
            )
        )
        .order_by(Section.section_name)
    )
    return list(db.execute(stmt).all())
