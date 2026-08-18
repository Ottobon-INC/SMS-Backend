# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Academic structure module router.

Responsibilities for this layer are documented in the architecture docs.
"""
import json
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

router = APIRouter(prefix="/academic-structure", tags=["academic_structure"])

DEFAULT_TENANT_ID = UUID("e0bb112a-1da7-44e2-8988-a90dc7b5cca5")
DEFAULT_USER_ID = UUID("842021d3-9826-4c4f-ad83-504be45d4520")

@router.get("/academic-years")
def get_academic_years(db: Session = Depends(get_db_session)):
    query = text("""
        SELECT id, code, name, starts_on, ends_on, status, is_default
        FROM sms_academic_years
        WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
        ORDER BY is_default DESC, starts_on DESC
    """)
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID}).fetchall()
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "name": r.name,
            "startsOn": r.starts_on.isoformat(),
            "endsOn": r.ends_on.isoformat(),
            "status": r.status,
            "isDefault": r.is_default,
        }
        for r in rows
    ]

@router.post("/academic-years")
def create_academic_year(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = str(DEFAULT_TENANT_ID)
    user_id = str(DEFAULT_USER_ID)
    ay_id = payload.get("id") or str(uuid.uuid4())
    name = payload.get("name") or "2026-2027"
    code = payload.get("code") or (name.replace("20", "") if len(name) == 9 else name)
    starts_on = payload.get("startsOn") or payload.get("starts_on") or f"{name[:4]}-06-01"
    ends_on = payload.get("endsOn") or payload.get("ends_on") or f"20{code[-2:] if len(code)>=2 else '27'}-04-30"
    is_default = bool(payload.get("isDefault"))

    if is_default:
        db.execute(
            text("UPDATE sms_academic_years SET is_default = false WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )

    query = text("""
        INSERT INTO sms_academic_years (
            id, tenant_id, code, name, starts_on, ends_on, status, is_default, created_by, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, CAST(:starts_on AS date), CAST(:ends_on AS date), 'ACTIVE', :is_default, :created_by, NOW(), NOW()
        )
        RETURNING id, code, name, starts_on, ends_on, status, is_default
    """)
    res = db.execute(
        query,
        {
            "id": ay_id,
            "tenant_id": tenant_id,
            "code": code,
            "name": name,
            "starts_on": starts_on,
            "ends_on": ends_on,
            "is_default": is_default,
            "created_by": user_id,
        },
    ).fetchone()
    db.commit()

    return {
        "id": str(res.id),
        "code": res.code,
        "name": res.name,
        "startsOn": res.starts_on.isoformat(),
        "endsOn": res.ends_on.isoformat(),
        "status": res.status,
        "isDefault": res.is_default,
    }

@router.patch("/academic-years/{ay_id}/default")
def set_default_academic_year(ay_id: UUID, db: Session = Depends(get_db_session)):
    tenant_id = str(DEFAULT_TENANT_ID)
    db.execute(
        text("UPDATE sms_academic_years SET is_default = false WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    db.execute(
        text("UPDATE sms_academic_years SET is_default = true, updated_at = NOW() WHERE id = :ay_id AND tenant_id = :tenant_id"),
        {"ay_id": ay_id, "tenant_id": tenant_id},
    )
    db.commit()
    return {"status": "ok", "message": f"Academic year {ay_id} set as default."}


@router.get("/subjects")
def get_subjects(db: Session = Depends(get_db_session)):
    query = text("""
        SELECT
            id,
            subject_code AS code,
            subject_name AS name,
            subject_type,
            COALESCE((metadata->>'maxMarks')::int, 100) AS max_marks,
            COALESCE((metadata->>'passMarks')::int, 35) AS pass_marks
        FROM sms_subjects
        WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
        ORDER BY subject_code
    """)
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID}).fetchall()
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "name": r.name,
            "subjectType": r.subject_type,
            "maxMarks": r.max_marks,
            "passMarks": r.pass_marks,
        }
        for r in rows
    ]

@router.post("/subjects")
def create_subject(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = str(DEFAULT_TENANT_ID)
    user_id = str(DEFAULT_USER_ID)
    sub_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or "SUB-101"
    name = payload.get("name") or "New Subject"
    subject_type = payload.get("type") or payload.get("subjectType") or "CORE"
    max_marks = int(payload.get("maxMarks") or 100)
    pass_marks = int(payload.get("passMarks") or 35)
    
    query = text("""
        INSERT INTO sms_subjects (
            id, tenant_id, subject_code, subject_name, subject_type, status,
            metadata, created_by, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, :subject_type, 'ACTIVE',
            jsonb_build_object('maxMarks', :max_marks, 'passMarks', :pass_marks),
            :created_by, NOW(), NOW()
        )
        RETURNING
            id,
            subject_code AS code,
            subject_name AS name,
            subject_type,
            COALESCE((metadata->>'maxMarks')::int, 100) AS max_marks,
            COALESCE((metadata->>'passMarks')::int, 35) AS pass_marks
    """)
    res = db.execute(
        query,
        {
            "id": sub_id,
            "tenant_id": tenant_id,
            "code": code,
            "name": name,
            "subject_type": subject_type,
            "max_marks": max_marks,
            "pass_marks": pass_marks,
            "created_by": user_id,
        },
    ).fetchone()
    db.commit()
    return {
        "id": str(res.id),
        "code": res.code,
        "name": res.name,
        "subjectType": res.subject_type,
        "maxMarks": res.max_marks,
        "passMarks": res.pass_marks,
    }

@router.get("/programmes")
def get_programmes(db: Session = Depends(get_db_session)):
    query = text("""
        SELECT
            id,
            programme_code AS code,
            programme_name AS name,
            coaching_track,
            COALESCE(metadata->>'yearLevel', 'First Year') AS year_level,
            COALESCE(metadata->'subjectIds', '[]'::jsonb) AS subject_ids
        FROM sms_academic_programmes
        WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
        ORDER BY programme_code
    """)
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID}).fetchall()
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "name": r.name,
            "coachingTrack": r.coaching_track,
            "yearLevel": r.year_level,
            "subjectIds": r.subject_ids or [],
        }
        for r in rows
    ]

@router.post("/programmes")
def create_programme(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = str(DEFAULT_TENANT_ID)
    user_id = str(DEFAULT_USER_ID)
    prog_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or "STREAM"
    name = payload.get("name") or "Course Stream"
    coaching_track = payload.get("coachingTrack")
    year_level = payload.get("yearLevel") or "First Year"
    subject_ids = payload.get("subjectIds") or []
    
    query = text("""
        INSERT INTO sms_academic_programmes (
            id, tenant_id, programme_code, programme_name, stream_code,
            coaching_track, duration_years, status, metadata, created_by,
            created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, :code,
            :coaching_track, 2, 'ACTIVE',
            jsonb_build_object('yearLevel', :year_level, 'subjectIds', CAST(:subject_ids AS jsonb)),
            :created_by, NOW(), NOW()
        )
        RETURNING
            id,
            programme_code AS code,
            programme_name AS name,
            coaching_track,
            COALESCE(metadata->>'yearLevel', 'First Year') AS year_level,
            COALESCE(metadata->'subjectIds', '[]'::jsonb) AS subject_ids
    """)
    res = db.execute(
        query,
        {
            "id": prog_id,
            "tenant_id": tenant_id,
            "code": code,
            "name": name,
            "coaching_track": coaching_track,
            "year_level": year_level,
            "subject_ids": json.dumps(subject_ids),
            "created_by": user_id,
        },
    ).fetchone()
    db.commit()
    return {
        "id": str(res.id),
        "code": res.code,
        "name": res.name,
        "coachingTrack": res.coaching_track,
        "yearLevel": res.year_level,
        "subjectIds": res.subject_ids or [],
    }
