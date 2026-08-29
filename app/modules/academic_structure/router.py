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

from app.core.security.context import RequestContext
from app.core.security.dependencies import require_permission
from app.modules.academic_structure.constants import (
    DEFAULT_SUBJECTS_BY_STREAM,
    ALLOWED_STREAM_TRACKS,
    STREAM_LABELS,
    normalize_stream_code,
    normalize_track,
    programme_code_for,
    programme_display_label,
    programme_response_from_row,
    validate_stream_track,
)

router = APIRouter(prefix="/academic-structure", tags=["academic_structure"])

ACADEMIC_STRUCTURE_VIEW = "academic_structure.view"
ACADEMIC_STRUCTURE_MANAGE = "academic_structure.manage"


def _require_tenant_context(context: RequestContext) -> UUID:
    if context.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant scope required.")
    return context.tenant_id


def _require_tenant_wide_context(context: RequestContext) -> UUID:
    tenant_id = _require_tenant_context(context)
    if context.branch_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant-wide academic governance scope required.")
    return tenant_id


@router.get("/academic-years")
def get_academic_years(
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_VIEW)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
    user_id = context.app_user_id
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_VIEW)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
    user_id = context.app_user_id
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_VIEW)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
    query = text("""
        SELECT
            id,
            programme_code AS code,
            programme_name AS name,
            stream_code,
            coaching_track,
            COALESCE(metadata->>'yearLevel', 'First Year') AS year_level,
            COALESCE(metadata->'subjectIds', '[]'::jsonb) AS subject_ids
        FROM sms_academic_programmes
        WHERE tenant_id = :tenant_id AND status = 'ACTIVE'
        ORDER BY programme_code
    """)
    rows = db.execute(query, {"tenant_id": tenant_id}).fetchall()

    return [programme_response_from_row(r) for r in rows]


@router.get("/programme-options")
def get_programme_options(
    _: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_VIEW)),
):
    return {
        "streams": [
            {
                "code": code,
                "label": label,
                "defaultSubjects": list(DEFAULT_SUBJECTS_BY_STREAM.get(code, ())),
                "allowedTracks": list(ALLOWED_STREAM_TRACKS[code]),
            }
            for code, label in STREAM_LABELS.items()
        ],
        "coachingTracks": sorted({track for tracks in ALLOWED_STREAM_TRACKS.values() for track in tracks}),
    }

@router.post("/programmes")
def create_programme(
    payload: dict,
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
    user_id = context.app_user_id
    tenant_id_str = str(tenant_id)
    user_id_str = str(user_id)

    prog_id = payload.get("id") or str(uuid.uuid4())
    stream_code = normalize_stream_code(payload.get("streamCode") or payload.get("stream_code") or payload.get("code"))
    coaching_track = normalize_track(payload.get("coachingTrack") or payload.get("coaching_track"))
    try:
        validate_stream_track(stream_code, coaching_track)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    code = programme_code_for(stream_code, coaching_track)
    name = programme_display_label(
        programme_code=code,
        programme_name=None,
        stream_code=stream_code,
        coaching_track=coaching_track,
    )
    subject_ids = payload.get("subjectIds") or []
    metadata_json = json.dumps({"subjectIds": subject_ids})

    duplicate = db.execute(
        text("""
            SELECT id
            FROM sms_academic_programmes
            WHERE tenant_id = :tenant_id
                AND status = 'ACTIVE'
                AND (
                    upper(programme_code) = upper(:code)
                    OR (upper(stream_code) = upper(:stream_code) AND lower(coaching_track) = lower(:coaching_track))
                )
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id_str,
            "code": code,
            "stream_code": stream_code,
            "coaching_track": coaching_track,
        },
    ).fetchone()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Course stream group {name} already exists.",
        )

    query = text("""
        INSERT INTO sms_academic_programmes (
            id, tenant_id, programme_code, programme_name, stream_code,
            coaching_track, duration_years, status, metadata, created_by,
            created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, :stream_code,
            :coaching_track, 2, 'ACTIVE',
            CAST(:metadata AS jsonb),
            :created_by, NOW(), NOW()
        )
        RETURNING
            id,
            programme_code AS code,
            programme_name AS name,
            stream_code,
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
            "stream_code": stream_code,
            "coaching_track": coaching_track,
            "metadata": metadata_json,
            "created_by": user_id_str,
        },
    ).fetchone()

    db.commit()
    return programme_response_from_row(res)


@router.patch("/programmes/{programme_id}")
def update_programme(
    programme_id: UUID,
    payload: dict,
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
    user_id = context.app_user_id
    existing = db.execute(
        text("""
            SELECT
                id,
                programme_code,
                programme_name,
                stream_code,
                coaching_track,
                COALESCE(metadata->>'yearLevel', 'First Year') AS year_level,
                COALESCE(metadata->'subjectIds', '[]'::jsonb) AS subject_ids,
                status
            FROM sms_academic_programmes
            WHERE tenant_id = :tenant_id AND id = :programme_id
            LIMIT 1
        """),
        {"tenant_id": tenant_id, "programme_id": programme_id},
    ).fetchone()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course stream group not found.")

    requested_stream = payload.get("streamCode") or payload.get("stream_code")
    requested_track = payload.get("coachingTrack") or payload.get("coaching_track")
    stream_code = normalize_stream_code(requested_stream) if requested_stream is not None else existing.stream_code
    coaching_track = normalize_track(requested_track) if requested_track is not None else existing.coaching_track
    identity_changed = stream_code != existing.stream_code or coaching_track != existing.coaching_track

    if identity_changed:
        dependent_count = db.execute(
            text("""
                SELECT
                    (SELECT COUNT(*) FROM sms_batches WHERE tenant_id = :tenant_id AND programme_id = :programme_id)
                    + (SELECT COUNT(*) FROM sms_enrollments WHERE tenant_id = :tenant_id AND programme_id = :programme_id)
                    + (SELECT COUNT(*) FROM sms_exams WHERE tenant_id = :tenant_id AND (programme_id = :programme_id OR programme_ids ? CAST(:programme_id AS text)))
                    + (
                        SELECT COUNT(*)
                        FROM sms_fee_accounts fa
                        JOIN sms_enrollments e
                            ON e.tenant_id = fa.tenant_id
                            AND e.id = fa.enrollment_id
                        WHERE fa.tenant_id = :tenant_id
                            AND e.programme_id = :programme_id
                    ) AS dependency_count
            """),
            {"tenant_id": tenant_id, "programme_id": programme_id},
        ).scalar() or 0
        if dependent_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This course stream group already has academic records. Create a new group instead of changing its stream or track.",
            )
        try:
            validate_stream_track(stream_code, coaching_track)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    code = programme_code_for(stream_code, coaching_track)
    name = programme_display_label(
        programme_code=code,
        programme_name=None,
        stream_code=stream_code,
        coaching_track=coaching_track,
    )
    subject_ids = payload.get("subjectIds", existing.subject_ids or [])
    status_value = payload.get("status") or existing.status
    if status_value not in {"ACTIVE", "INACTIVE"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid programme status.")

    duplicate = db.execute(
        text("""
            SELECT id
            FROM sms_academic_programmes
            WHERE tenant_id = :tenant_id
                AND id <> :programme_id
                AND status = 'ACTIVE'
                AND upper(programme_code) = upper(:code)
            LIMIT 1
        """),
        {"tenant_id": tenant_id, "programme_id": programme_id, "code": code},
    ).fetchone()
    if duplicate is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Course stream group {name} already exists.")

    metadata_json = json.dumps({"subjectIds": subject_ids})
    row = db.execute(
        text("""
            UPDATE sms_academic_programmes
            SET programme_code = :code,
                programme_name = :name,
                stream_code = :stream_code,
                coaching_track = :coaching_track,
                status = :status,
                metadata = CAST(:metadata AS jsonb),
                updated_by = :updated_by,
                updated_at = NOW()
            WHERE tenant_id = :tenant_id AND id = :programme_id
            RETURNING
                id,
                programme_code AS code,
                programme_name AS name,
                stream_code,
                coaching_track,
                COALESCE(metadata->>'yearLevel', 'First Year') AS year_level,
                COALESCE(metadata->'subjectIds', '[]'::jsonb) AS subject_ids
        """),
        {
            "tenant_id": tenant_id,
            "programme_id": programme_id,
            "code": code,
            "name": name,
            "stream_code": stream_code,
            "coaching_track": coaching_track,
            "status": status_value,
            "metadata": metadata_json,
            "updated_by": user_id,
        },
    ).fetchone()
    db.commit()
    return programme_response_from_row(row)


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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_VIEW)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
    if context.branch_id is not None and context.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this branch.")
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
    context: RequestContext = Depends(require_permission(ACADEMIC_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_wide_context(context)
    user_id = context.app_user_id
    batch_id = payload.get("batchId") or payload.get("batch_id")
    section_suffix = _clean_section_suffix(payload.get("section") or payload.get("sectionName") or "")
    capacity = payload.get("capacity")

    batch = db.execute(
        text("""
            SELECT
                bt.id,
                bt.branch_id,
                bt.year_level,
                p.programme_code,
                p.stream_code
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

    section_display_prefix = batch.stream_code or batch.programme_code.split("-", 1)[0]
    section_code = f"{batch.programme_code}-{batch.year_level}{section_suffix}"
    section_name = f"{section_display_prefix}-{section_suffix}"

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
