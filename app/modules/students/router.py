# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Students module router providing student endpoints."""

import uuid
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.dependencies import require_any_permission, resolve_tenant_id, resolve_user_id

router = APIRouter(prefix="/students", tags=["students"])

STUDENT_UPDATE_PERMISSIONS = {"student.update_basic", "student.update_sensitive"}



class StudentInlineUpdateRequest(BaseModel):
    student_name: str | None = Field(default=None, min_length=1, max_length=200)
    gender: str | None = Field(default=None, pattern="^(MALE|FEMALE|OTHER)$")
    date_of_birth: date | None = None
    student_mobile: str | None = Field(default=None, max_length=30)
    student_email: str | None = Field(default=None, max_length=320)
    roll_number: str | None = Field(default=None, max_length=60)
    joining_date: date | None = None
    ending_date: date | None = None
    guardian_name: str | None = Field(default=None, min_length=1, max_length=200)
    guardian_relationship: str | None = Field(default=None, pattern="^(FATHER|MOTHER|LEGAL_GUARDIAN|RELATIVE|SPONSOR|OTHER)$")
    guardian_phone: str | None = Field(default=None, max_length=30)
    guardian_email: str | None = Field(default=None, max_length=320)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _fetch_student_scope(db: Session, student_id: UUID, tenant_id: UUID) -> Any | None:
    return db.execute(
        text("""
            SELECT
                s.id AS student_id,
                s.tenant_id,
                e.id AS enrollment_id,
                e.branch_id,
                g.id AS guardian_id,
                sgl.id AS guardian_link_id
            FROM sms_students s
            LEFT JOIN sms_enrollments e
                ON e.tenant_id = s.tenant_id
                AND e.student_id = s.id
                AND e.is_current = true
            LEFT JOIN sms_student_guardian_links sgl
                ON sgl.tenant_id = s.tenant_id
                AND sgl.student_id = s.id
                AND sgl.is_primary = true
                AND sgl.status = 'ACTIVE'
            LEFT JOIN sms_guardians g
                ON g.tenant_id = sgl.tenant_id
                AND g.id = sgl.guardian_id
            WHERE s.id = :student_id
                AND s.tenant_id = :tenant_id
        """),
        {"student_id": student_id, "tenant_id": tenant_id},
    ).fetchone()


@router.get("")
@router.get("/")
def get_students(
    branch_id: str | None = None,
    section_id: str | None = None,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    query = text("""
        SELECT
            s.id,
            s.tenant_id,
            s.student_number,
            s.legal_name,
            s.display_name,
            s.gender,
            s.date_of_birth,
            s.student_mobile,
            s.student_email,
            s.current_status,
            e.id AS enrollment_id,
            e.admission_number,
            e.roll_number,
            e.year_level,
            e.status AS enrollment_status,
            e.joining_date,
            e.ending_date,
            b.id AS branch_id,
            b.display_name AS branch_name,
            sec.id AS section_id,
            sec.section_name AS section,
            g.full_name AS guardian_name,
            g.mobile AS guardian_phone,
            sgl.relationship_type AS guardian_relationship

        FROM sms_students s
        LEFT JOIN sms_enrollments e
            ON e.tenant_id = s.tenant_id AND e.student_id = s.id AND e.status = 'ACTIVE'
        LEFT JOIN sms_branches b ON b.id = e.branch_id
        LEFT JOIN sms_sections sec ON sec.id = e.section_id
        LEFT JOIN sms_student_guardian_links sgl
            ON sgl.tenant_id = s.tenant_id AND sgl.student_id = s.id AND sgl.is_primary = true
        LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id
        WHERE s.tenant_id = :tenant_id
            AND s.current_status = 'ACTIVE'
            AND (CAST(:branch_id AS uuid) IS NULL OR e.branch_id = CAST(:branch_id AS uuid))
            AND (CAST(:section_id AS uuid) IS NULL OR e.section_id = CAST(:section_id AS uuid))
        ORDER BY s.created_at DESC
    """)
    rows = db.execute(query, {"tenant_id": str(tenant_id), "branch_id": branch_id, "section_id": section_id}).fetchall()

    def to_iso(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    return [
        {
            "id": str(r.id),
            "tenantId": str(r.tenant_id),
            "studentNumber": r.student_number,
            "admissionNumber": r.admission_number or r.student_number or "N/A",
            "name": r.display_name or r.legal_name,
            "displayName": r.display_name or r.legal_name,
            "legalName": r.legal_name,
            "rollNo": r.roll_number or "-",
            "rollNumber": r.roll_number,
            "gender": r.gender or "-",
            "dob": to_iso(r.date_of_birth),
            "studentMobile": r.student_mobile,
            "studentEmail": r.student_email,
            "branchId": str(r.branch_id) if r.branch_id else None,
            "branchName": r.branch_name,
            "sectionId": str(r.section_id) if r.section_id else None,
            "sectionName": r.section,
            "section": r.section or "-",
            "status": r.current_status,
            "guardian": {
                "name": r.guardian_name or "Guardian Name",
                "mobile": r.guardian_phone or "+91 98765 00000",
                "relationship": r.guardian_relationship or "GUARDIAN",
            },
        }
        for r in rows
    ]



@router.patch("/{student_id}")
def update_student_inline(
    student_id: UUID,
    payload: StudentInlineUpdateRequest,
    context: RequestContext = Depends(require_any_permission(STUDENT_UPDATE_PERMISSIONS)),
    db: Session = Depends(get_db_session),
):
    if context.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant scope required.")

    scope = _fetch_student_scope(db, student_id, context.tenant_id)
    if scope is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
    if context.branch_id is not None and scope.branch_id is not None and scope.branch_id != context.branch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return {"status": "ok", "message": "No changes submitted."}

    try:
        student_updates: dict[str, Any] = {
            "student_id": student_id,
            "tenant_id": context.tenant_id,
            "updated_by": context.app_user_id,
        }
        student_set_clauses = ["updated_by = :updated_by", "updated_at = NOW()"]
        if "student_name" in changes:
            student_updates["student_name"] = _normalize_optional_text(payload.student_name)
            student_set_clauses.extend(["legal_name = :student_name", "display_name = :student_name"])
        if "gender" in changes:
            student_updates["gender"] = payload.gender
            student_set_clauses.append("gender = :gender")
        if "date_of_birth" in changes:
            student_updates["date_of_birth"] = payload.date_of_birth
            student_set_clauses.append("date_of_birth = :date_of_birth")
        if "student_mobile" in changes:
            student_updates["student_mobile"] = _normalize_optional_text(payload.student_mobile)
            student_set_clauses.append("student_mobile = :student_mobile")
        if "student_email" in changes:
            student_updates["student_email"] = _normalize_optional_text(payload.student_email)
            student_set_clauses.append("student_email = :student_email")
        if len(student_set_clauses) > 2:
            db.execute(
                text(f"""
                    UPDATE sms_students
                    SET {", ".join(student_set_clauses)}
                    WHERE id = :student_id
                        AND tenant_id = :tenant_id
                """),
                student_updates,
            )

        enrollment_updates: dict[str, Any] = {
            "enrollment_id": scope.enrollment_id,
            "tenant_id": context.tenant_id,
            "updated_by": context.app_user_id,
        }
        enrollment_set_clauses = ["updated_by = :updated_by", "updated_at = NOW()"]
        if scope.enrollment_id is not None:
            if "roll_number" in changes:
                enrollment_updates["roll_number"] = _normalize_optional_text(payload.roll_number)
                enrollment_set_clauses.append("roll_number = :roll_number")
            if "joining_date" in changes:
                enrollment_updates["joining_date"] = payload.joining_date
                enrollment_set_clauses.append("joining_date = :joining_date")
            if "ending_date" in changes:
                enrollment_updates["ending_date"] = payload.ending_date
                enrollment_set_clauses.append("ending_date = :ending_date")
            if len(enrollment_set_clauses) > 2:
                db.execute(
                    text(f"""
                        UPDATE sms_enrollments
                        SET {", ".join(enrollment_set_clauses)}
                        WHERE id = :enrollment_id
                            AND tenant_id = :tenant_id
                    """),
                    enrollment_updates,
                )

        guardian_updates: dict[str, Any] = {
            "guardian_id": scope.guardian_id,
            "tenant_id": context.tenant_id,
            "updated_by": context.app_user_id,
        }
        guardian_set_clauses = ["updated_by = :updated_by", "updated_at = NOW()"]
        if scope.guardian_id is not None:
            if "guardian_name" in changes:
                guardian_updates["guardian_name"] = _normalize_optional_text(payload.guardian_name)
                guardian_set_clauses.append("full_name = :guardian_name")
            if "guardian_phone" in changes:
                guardian_updates["guardian_phone"] = _normalize_optional_text(payload.guardian_phone)
                guardian_set_clauses.append("mobile = :guardian_phone")
            if "guardian_email" in changes:
                guardian_updates["guardian_email"] = _normalize_optional_text(payload.guardian_email)
                guardian_set_clauses.append("email = :guardian_email")
            if len(guardian_set_clauses) > 2:
                db.execute(
                    text(f"""
                        UPDATE sms_guardians
                        SET {", ".join(guardian_set_clauses)}
                        WHERE id = :guardian_id
                            AND tenant_id = :tenant_id
                    """),
                    guardian_updates,
                )

        if scope.guardian_link_id is not None and "guardian_relationship" in changes:
            db.execute(
                text("""
                    UPDATE sms_student_guardian_links
                    SET
                        relationship_type = COALESCE(:guardian_relationship, relationship_type),
                        updated_by = :updated_by,
                        updated_at = NOW()
                    WHERE id = :guardian_link_id
                        AND tenant_id = :tenant_id
                """),
                {
                    "guardian_link_id": scope.guardian_link_id,
                    "tenant_id": context.tenant_id,
                    "updated_by": context.app_user_id,
                    "guardian_relationship": payload.guardian_relationship,
                },
            )

        db.commit()
        return {"status": "ok", "message": "Student data updated."}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update student data: {exc}") from exc


@router.post("")
@router.post("/")
def create_student(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    student_id = payload.get("id") or str(uuid.uuid4())
    student_number = payload.get("admissionNumber") or payload.get("student_number") or f"STU-{uuid.uuid4().hex[:8].upper()}"
    name = payload.get("name") or payload.get("legal_name") or "New Student"
    gender = payload.get("gender") or "MALE"
    dob = payload.get("dob") or payload.get("date_of_birth") or "2008-01-01"

    query = text("""
        INSERT INTO sms_students (
            id, tenant_id, student_number, legal_name, display_name,
            date_of_birth, gender, current_status, admission_type, created_by, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :student_number, :name, :name,
            CAST(:dob AS date), :gender, 'ACTIVE', 'MANUAL', :created_by, NOW(), NOW()
        )
        RETURNING id, student_number, legal_name, display_name, gender, date_of_birth, current_status
    """)
    res = db.execute(
        query,
        {
            "id": student_id,
            "tenant_id": str(tenant_id),
            "student_number": student_number,
            "name": name,
            "dob": dob,
            "gender": gender,
            "created_by": str(user_id),
        },
    ).fetchone()

    db.commit()

    if res is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create student")

    return {
        "id": str(res.id),
        "admissionNumber": res.student_number,
        "name": res.display_name or res.legal_name,
        "rollNo": payload.get("rollNo") or payload.get("roll_number") or "-",
        "gender": res.gender,
        "dob": res.date_of_birth.isoformat() if hasattr(res.date_of_birth, "isoformat") else str(res.date_of_birth),
        "stream": payload.get("stream") or "MPC",
        "section": payload.get("section") or "MPC-A",
        "bloodGroup": payload.get("bloodGroup") or "N/A",
        "status": res.current_status,
        "guardian": payload.get("guardian")
        or {
            "name": "Guardian Name",
            "mobile": "+91 98765 00000",
            "relationship": "GUARDIAN",
        },
    }
