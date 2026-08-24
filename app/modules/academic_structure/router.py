# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Academic structure module router.

Responsibilities for this layer are documented in the architecture docs.
"""
import json
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

from app.core.security.dependencies import resolve_tenant_id, resolve_user_id

router = APIRouter(prefix="/academic-structure", tags=["academic_structure"])

@router.get("/academic-years")
def get_academic_years(
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    query = text("""
        SELECT id, code, name, starts_on, ends_on, status, is_default
        FROM sms_academic_years
        WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
        ORDER BY is_default DESC, starts_on DESC
    """)
    rows = db.execute(query, {"tenant_id": tenant_id}).fetchall()

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
def create_academic_year(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_str = str(tenant_id)
    user_id_str = str(user_id)

    ay_id = payload.get("id") or str(uuid.uuid4())
    name = payload.get("name") or "2026-2027"
    code = payload.get("code") or (name.replace("20", "") if len(name) == 9 else name)
    starts_on = payload.get("startsOn") or payload.get("starts_on") or f"{name[:4]}-06-01"
    ends_on = payload.get("endsOn") or payload.get("ends_on") or f"20{code[-2:] if len(code)>=2 else '27'}-04-30"
    is_default = bool(payload.get("isDefault"))

    if is_default:
        db.execute(
            text("UPDATE sms_academic_years SET is_default = false WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id_str},
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
            "tenant_id": tenant_id_str,
            "code": code,
            "name": name,
            "starts_on": starts_on,
            "ends_on": ends_on,
            "is_default": is_default,
            "created_by": user_id_str,
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
def set_default_academic_year(
    ay_id: UUID,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_str = str(tenant_id)
    db.execute(
        text("UPDATE sms_academic_years SET is_default = false WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id_str},
    )
    db.execute(
        text("UPDATE sms_academic_years SET is_default = true, updated_at = NOW() WHERE id = :ay_id AND tenant_id = :tenant_id"),
        {"ay_id": ay_id, "tenant_id": tenant_id_str},
    )

    db.commit()
    return {"status": "ok", "message": f"Academic year {ay_id} set as default."}


@router.get("/subjects")
def get_subjects(
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
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
    rows = db.execute(query, {"tenant_id": tenant_id}).fetchall()

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
def create_subject(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_str = str(tenant_id)
    user_id_str = str(user_id)

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
            "tenant_id": tenant_id_str,
            "code": code,
            "name": name,
            "subject_type": subject_type,
            "max_marks": max_marks,
            "pass_marks": pass_marks,
            "created_by": user_id_str,
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
def get_programmes(
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
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
    rows = db.execute(query, {"tenant_id": tenant_id}).fetchall()

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
def create_programme(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_str = str(tenant_id)
    user_id_str = str(user_id)

    prog_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or "STREAM"
    name = payload.get("name") or "Course Stream"
    coaching_track = payload.get("coachingTrack")
    year_level = payload.get("yearLevel") or "First Year"
    subject_ids = payload.get("subjectIds") or []
    metadata_json = json.dumps({"yearLevel": year_level, "subjectIds": subject_ids})

    query = text("""
        INSERT INTO sms_academic_programmes (
            id, tenant_id, programme_code, programme_name, stream_code,
            coaching_track, duration_years, status, metadata, created_by,
            created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, :code,
            :coaching_track, 2, 'ACTIVE',
            CAST(:metadata AS jsonb),
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
            "tenant_id": tenant_id_str,
            "code": code,
            "name": name,
            "coaching_track": coaching_track,
            "metadata": metadata_json,
            "created_by": user_id_str,
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


def _clean_section_suffix(value: str) -> str:
    suffix = (value or "").strip().upper()
    if suffix.startswith("SECTION "):
        suffix = suffix.replace("SECTION ", "", 1).strip()
    if not suffix or len(suffix) > 3 or not suffix.isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Section must be 1 to 3 letters or numbers, such as A, B, or C.",
        )
    return suffix


def _display_section_name(section_name: str, section_code: str) -> str:
    value = section_name or section_code
    parts = value.split("-")
    if len(parts) >= 2 and parts[1][:1] in {"1", "2"}:
        return f"{parts[0]}-{parts[1][1:]}"
    return value


@router.get("/sections")
def get_academic_sections(
    branch_id: UUID,
    academic_year_id: UUID,
    programme_id: UUID,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    rows = db.execute(
        text("""
            SELECT
                bt.id AS batch_id,
                bt.batch_code,
                bt.batch_name,
                bt.year_level,
                s.id AS section_id,
                s.section_code,
                s.section_name,
                s.capacity,
                s.status AS section_status
            FROM sms_batches bt
            LEFT JOIN sms_sections s
                ON s.tenant_id = bt.tenant_id
                AND s.branch_id = bt.branch_id
                AND s.batch_id = bt.id
                AND s.status = 'ACTIVE'
            WHERE bt.tenant_id = :tenant_id
                AND bt.branch_id = :branch_id
                AND bt.academic_year_id = :academic_year_id
                AND bt.programme_id = :programme_id
                AND bt.status = 'ACTIVE'
            ORDER BY bt.year_level, bt.batch_name, s.section_name
        """),
        {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "academic_year_id": academic_year_id,
            "programme_id": programme_id,
        },
    ).fetchall()

    batches: dict[str, dict] = {}
    for row in rows:
        batch_id = str(row.batch_id)
        batches.setdefault(
            batch_id,
            {
                "id": batch_id,
                "code": row.batch_code,
                "name": row.batch_name,
                "yearLevel": row.year_level,
                "sections": [],
            },
        )
        if row.section_id:
            batches[batch_id]["sections"].append(
                {
                    "id": str(row.section_id),
                    "code": row.section_code,
                    "name": _display_section_name(row.section_name, row.section_code),
                    "capacity": row.capacity,
                    "status": row.section_status,
                }
            )

    return list(batches.values())


@router.post("/sections")
def create_academic_section(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    batch_id = payload.get("batchId") or payload.get("batch_id")
    section_suffix = _clean_section_suffix(payload.get("section") or payload.get("sectionName") or "")
    capacity = payload.get("capacity")

    batch = db.execute(
        text("""
            SELECT
                bt.id,
                bt.branch_id,
                bt.year_level,
                p.programme_code
            FROM sms_batches bt
            JOIN sms_academic_programmes p
                ON p.tenant_id = bt.tenant_id
                AND p.id = bt.programme_id
            WHERE bt.tenant_id = :tenant_id
                AND bt.id = :batch_id
                AND bt.status = 'ACTIVE'
                AND p.status = 'ACTIVE'
        """),
        {"tenant_id": tenant_id, "batch_id": batch_id},
    ).fetchone()
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active batch not found.")

    section_code = f"{batch.programme_code}-{batch.year_level}{section_suffix}"
    section_name = f"{batch.programme_code}-{section_suffix}"

    existing = db.execute(
        text("""
            SELECT id
            FROM sms_sections
            WHERE tenant_id = :tenant_id
                AND branch_id = :branch_id
                AND batch_id = :batch_id
                AND (
                    upper(section_code) = upper(:section_code)
                    OR upper(section_name) = upper(:section_name)
                    OR upper(regexp_replace(section_code, '-[[:xdigit:]]{4}$', '')) = upper(:section_code)
                    OR upper(regexp_replace(section_name, '-([12])([[:alnum:]]+)$', '-\\2')) = upper(:section_name)
                )
                AND status = 'ACTIVE'
        """),
        {
            "tenant_id": tenant_id,
            "branch_id": batch.branch_id,
            "batch_id": batch.id,
            "section_code": section_code,
            "section_name": section_name,
        },
    ).fetchone()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Section {section_name} already exists for this batch.",
        )

    row = db.execute(
        text("""
            INSERT INTO sms_sections (
                id, tenant_id, branch_id, batch_id, section_code, section_name,
                capacity, status, created_by, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :branch_id, :batch_id, :section_code, :section_name,
                :capacity, 'ACTIVE', :user_id, NOW(), NOW()
            )
            RETURNING id, section_code, section_name, capacity, status
        """),
        {
            "id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "branch_id": batch.branch_id,
            "batch_id": batch.id,
            "section_code": section_code,
            "section_name": section_name,
            "capacity": capacity,
            "user_id": user_id,
        },
    ).fetchone()
    db.commit()

    return {
        "id": str(row.id),
        "code": row.section_code,
        "name": row.section_name,
        "capacity": row.capacity,
        "status": row.status,
    }
