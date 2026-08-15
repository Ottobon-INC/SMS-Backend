# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Students module router providing student endpoints."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

router = APIRouter(prefix="/students", tags=["students"])

DEFAULT_TENANT_ID = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"
DEFAULT_USER_ID = "842021d3-9826-4c4f-ad83-504be45d4520"


@router.get("")
@router.get("/")
def get_students(branch_id: str | None = None, db: Session = Depends(get_db_session)):
    query = text("""
        SELECT
            s.id,
            s.student_number,
            e.admission_number,
            s.display_name,
            s.legal_name,
            s.gender,
            s.date_of_birth,
            s.current_status,
            e.roll_number,
            p.programme_name AS stream,
            sec.section_name AS section,
            g.full_name AS guardian_name,
            sgl.relationship_type AS guardian_relationship,
            g.mobile AS guardian_phone
        FROM sms_students s
        LEFT JOIN sms_enrollments e
            ON e.tenant_id = s.tenant_id
            AND e.student_id = s.id
            AND e.is_current = true
        LEFT JOIN sms_academic_programmes p
            ON p.tenant_id = e.tenant_id
            AND p.id = e.programme_id
        LEFT JOIN sms_sections sec
            ON sec.tenant_id = e.tenant_id
            AND sec.branch_id = e.branch_id
            AND sec.batch_id = e.batch_id
            AND sec.id = e.section_id
        LEFT JOIN sms_student_guardian_links sgl
            ON sgl.tenant_id = s.tenant_id
            AND sgl.student_id = s.id
            AND sgl.is_primary = true
            AND sgl.status = 'ACTIVE'
        LEFT JOIN sms_guardians g
            ON g.tenant_id = sgl.tenant_id
            AND g.id = sgl.guardian_id
        WHERE
            s.tenant_id = :tenant_id
            AND s.current_status = 'ACTIVE'
            AND (CAST(:branch_id AS uuid) IS NULL OR e.branch_id = CAST(:branch_id AS uuid))
        ORDER BY s.created_at DESC
    """)
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID, "branch_id": branch_id}).fetchall()

    return [
        {
            "id": str(r.id),
            "admissionNumber": r.admission_number or r.student_number or "N/A",
            "name": r.display_name or r.legal_name,
            "rollNo": r.roll_number or "-",
            "gender": r.gender or "-",
            "dob": r.date_of_birth.isoformat() if hasattr(r.date_of_birth, "isoformat") else str(r.date_of_birth),
            "stream": r.stream or "-",
            "section": r.section or "-",
            "bloodGroup": "N/A",
            "status": r.current_status,
            "father_name": r.guardian_name or "N/A",
            "guardian_relationship": r.guardian_relationship or "GUARDIAN",
            "guardian_phone": r.guardian_phone or "N/A",
            "guardian": {
                "name": r.guardian_name or "Guardian Name",
                "mobile": r.guardian_phone or "+91 98765 00000",
                "relationship": r.guardian_relationship or "GUARDIAN",
            },
        }
        for r in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_student(payload: dict, db: Session = Depends(get_db_session)):
    student_id = payload.get("id") or str(uuid.uuid4())
    student_number = payload.get("admissionNumber") or f"2026-STD-{uuid.uuid4().hex[:4].upper()}"
    name = payload.get("name") or "New Student"
    gender = payload.get("gender") or "MALE"
    dob = payload.get("dob") or payload.get("date_of_birth") or "2008-01-01"

    query = text("""
        INSERT INTO sms_students (
            id, tenant_id, student_number, legal_name, display_name,
            date_of_birth, gender, current_status, source_type, created_by, created_at, updated_at
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
            "tenant_id": DEFAULT_TENANT_ID,
            "student_number": student_number,
            "name": name,
            "dob": dob,
            "gender": gender,
            "created_by": DEFAULT_USER_ID,
        },
    ).fetchone()
    db.commit()

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
