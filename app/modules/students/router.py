"""Students module router providing student endpoints."""

import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

router = APIRouter(prefix="/students", tags=["students"])

DEFAULT_TENANT_ID = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"
DEFAULT_USER_ID = "842021d3-9826-4c4f-ad83-504be45d4520"


@router.get("")
@router.get("/")
def get_students(db: Session = Depends(get_db_session)):
    query = text("""
        SELECT
            s.id,
            s.student_number AS admission_number,
            s.legal_name AS name,
            s.gender,
            s.date_of_birth,
            s.current_status AS status,
            COALESCE(s.addresses, '{}'::jsonb) AS addresses
        FROM sms_students s
        WHERE s.tenant_id = :tenant_id AND s.current_status = 'ACTIVE'
        ORDER BY s.created_at DESC
    """)
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID}).fetchall()

    if not rows:
        return [
            {
                "id": "std-101",
                "admissionNumber": "2026-MPC-001",
                "name": "Rahul Verma",
                "gender": "MALE",
                "dob": "2008-05-14",
                "stream": "MPC",
                "section": "MPC-A",
                "bloodGroup": "O+",
                "status": "ACTIVE",
                "guardian": {
                    "name": "Suresh Verma",
                    "mobile": "+91 98765 11111",
                    "relationship": "FATHER",
                },
            },
            {
                "id": "std-102",
                "admissionNumber": "2026-BIPC-002",
                "name": "Ananya Sharma",
                "gender": "FEMALE",
                "dob": "2008-08-22",
                "stream": "BiPC",
                "section": "BIPC-A",
                "bloodGroup": "A+",
                "status": "ACTIVE",
                "guardian": {
                    "name": "Rajesh Sharma",
                    "mobile": "+91 98765 22222",
                    "relationship": "FATHER",
                },
            },
        ]

    return [
        {
            "id": str(r.id),
            "admissionNumber": r.admission_number,
            "name": r.name,
            "gender": r.gender,
            "dob": r.date_of_birth.isoformat() if hasattr(r.date_of_birth, "isoformat") else str(r.date_of_birth),
            "stream": "MPC",
            "section": "MPC-A",
            "bloodGroup": "O+",
            "status": r.status,
            "guardian": {
                "name": "Guardian Name",
                "mobile": "+91 98765 00000",
                "relationship": "FATHER",
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
    dob = payload.get("dob") or "2008-01-01"

    query = text("""
        INSERT INTO sms_students (
            id, tenant_id, student_number, legal_name, display_name,
            date_of_birth, gender, current_status, source_type, created_by, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :student_number, :name, :name,
            CAST(:dob AS date), :gender, 'ACTIVE', 'MANUAL', :created_by, NOW(), NOW()
        )
        RETURNING id, student_number, legal_name, gender, date_of_birth, current_status
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
        "name": res.legal_name,
        "gender": res.gender,
        "dob": res.date_of_birth.isoformat() if hasattr(res.date_of_birth, "isoformat") else str(res.date_of_birth),
        "stream": payload.get("stream") or "MPC",
        "section": payload.get("section") or "MPC-A",
        "bloodGroup": payload.get("bloodGroup") or "O+",
        "status": res.current_status,
        "guardian": payload.get("guardian") or {
            "name": "Guardian Name",
            "mobile": "+91 98765 00000",
            "relationship": "FATHER",
        },
    }
