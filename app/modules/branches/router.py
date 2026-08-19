# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Branches module router providing branch endpoints."""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

from uuid import UUID
from app.core.security.dependencies import resolve_tenant_id, resolve_user_id

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get("")
@router.get("/")
def get_branches(
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    query = text("""
        SELECT
            id,
            branch_code,
            display_name,
            legal_name,
            status,
            COALESCE(address_data, '{}'::jsonb) AS address_data,
            COALESCE(contact_data, '{}'::jsonb) AS contact_data,
            timezone
        FROM sms_branches
        WHERE tenant_id = :tenant_id AND status != 'INACTIVE'
        ORDER BY created_at DESC
    """)
    rows = db.execute(query, {"tenant_id": str(tenant_id)}).fetchall()


    if not rows:
        return [
            {
                "id": "8854ab2a-44cf-4770-bb51-5f78e0876e9d",
                "code": "MAIN",
                "name": "Main Campus",
                "branchCode": "MAIN",
                "displayName": "Main Campus",
                "legalName": "Development College Main Campus",
                "legal_name": "Development College Main Campus",
                "status": "ACTIVE",
                "address": {
                    "line1": "123 Main St",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "pincode": "500001",
                },
                "contact": {
                    "phone": "+91 98765 00001",
                    "email": "main@devcollege.edu",
                },
                "contact_person": "Not Assigned",
                "principalName": "Not Assigned",
            }
        ]

    res_list = []
    for r in rows:
        c_data = r.contact_data if isinstance(r.contact_data, dict) else json.loads(r.contact_data or "{}")

        # Query active user assignment from sms_user_access_assignments
        assign_row = db.execute(
            text("""
                SELECT u.id AS user_id, u.full_name
                FROM sms_user_access_assignments a
                JOIN sms_users u ON u.id = a.user_id
                WHERE a.branch_id = :b_id AND a.status = 'ACTIVE' AND a.is_primary = true
                LIMIT 1
            """),
            {"b_id": r.id},
        ).fetchone()

        p_id = str(assign_row.user_id) if assign_row else None
        p_name = assign_row.full_name if assign_row else "Not Assigned"

        res_list.append({
            "id": str(r.id),
            "code": r.branch_code,
            "name": r.display_name,
            "branchCode": r.branch_code,
            "displayName": r.display_name,
            "legalName": r.legal_name or r.display_name,
            "legal_name": r.legal_name or r.display_name,
            "status": r.status,
            "address": r.address_data if isinstance(r.address_data, dict) else json.loads(r.address_data or "{}"),
            "contact": c_data,
            "contact_person": p_name,
            "principalName": p_name,
            "principal_user_id": p_id,
        })

    return res_list



@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
@router.post("")
@router.post("/")
def create_branch(
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    user_role = payload.get("user_role") or payload.get("role") or ""
    if user_role == "BRANCH_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch creation is restricted to Institution Administrators (Deans). Principals cannot create campus branches.",
        )
    tenant_id_str = str(tenant_id)
    user_id_str = str(user_id)
    branch_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or payload.get("branchCode") or "BRANCH"
    display_name = payload.get("name") or payload.get("displayName") or "New Branch Campus"
    legal_name = payload.get("legalName") or payload.get("legal_name") or f"{display_name} Ltd"
    address = payload.get("address") or {
        "line1": "123 College Rd",
        "city": "Hyderabad",
        "state": "Telangana",
        "pincode": "500001",
    }
    contact_person = payload.get("contact_person") or payload.get("principalName") or "Not Assigned"

    contact = payload.get("contact") or {
        "phone": "+91 98765 00002",
        "email": "branch@devcollege.edu",
        "contact_person_name": contact_person,
    }

    query = text("""
        INSERT INTO sms_branches (
            id, tenant_id, branch_code, display_name, legal_name,
            status, address_data, contact_data, timezone,
            approved_by, approved_at, activated_at, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :display_name, :legal_name,
            'ACTIVE', CAST(:address_data AS jsonb), CAST(:contact_data AS jsonb), 'Asia/Kolkata',
            :user_id, NOW(), NOW(), NOW(), NOW()
        )
        RETURNING id, branch_code, display_name, legal_name, status, address_data, contact_data
    """)
    res = db.execute(
        query,
        {
            "id": branch_id,
            "tenant_id": tenant_id_str,
            "user_id": user_id_str,
            "code": code,
            "display_name": display_name,
            "legal_name": legal_name,
            "address_data": json.dumps(address),
            "contact_data": json.dumps(contact),
        },
    ).fetchone()
    db.commit()

    return {
        "id": str(res.id),
        "code": res.branch_code,
        "name": res.display_name,
        "branchCode": res.branch_code,
        "displayName": res.display_name,
        "legalName": res.legal_name,
        "legal_name": res.legal_name,
        "status": res.status,
        "address": address,
        "contact": contact,
        "contact_person": contact_person,
        "principalName": contact_person,
    }


@router.post("/{branch_id}/assign-principal")
def assign_principal(
    branch_id: str,
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_str = str(tenant_id)
    user_id = payload.get("user_id") or payload.get("principal_user_id")
    user_name = payload.get("user_name") or payload.get("contact_person_name") or "Assigned Principal"

    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")

    clear_old_branches = text("""
        UPDATE sms_branches
        SET contact_data = contact_data - 'contact_person_name' - 'contact_person',
            updated_at = NOW()
        WHERE tenant_id = :tenant_id
          AND id IN (
              SELECT branch_id FROM sms_user_access_assignments WHERE user_id = :user_id
          )
          AND id != :branch_id
    """)
    db.execute(clear_old_branches, {"tenant_id": tenant_id_str, "user_id": user_id, "branch_id": branch_id})

    deactivate_query = text("""
        UPDATE sms_user_access_assignments
        SET status = 'EXPIRED', valid_until = NOW(), is_primary = false
        WHERE user_id = :user_id AND status = 'ACTIVE' AND is_primary = true
    """)
    db.execute(deactivate_query, {"user_id": user_id})

    assign_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO sms_user_access_assignments (
            id, tenant_id, user_id, role_id, branch_id, scope_type, is_primary, status, assigned_by, valid_from, created_at, updated_at
        )
        SELECT
            :id, :tenant_id, :user_id, r.id, :branch_id, 'BRANCH', true, 'ACTIVE', :assigned_by, NOW(), NOW(), NOW()
        FROM sms_roles r
        WHERE r.role_code = 'BRANCH_ADMIN'
        LIMIT 1
    """)
    db.execute(
        insert_query,
        {
            "id": assign_id,
            "tenant_id": tenant_id_str,
            "user_id": user_id,
            "branch_id": branch_id,
            "assigned_by": user_id,
        },
    )

    update_branch = text("""
        UPDATE sms_branches
        SET contact_data = jsonb_set(
            COALESCE(contact_data, '{}'::jsonb),
            '{contact_person_name}',
            to_jsonb(CAST(:user_name AS text))
        ),
        updated_at = NOW()
        WHERE id = :branch_id AND tenant_id = :tenant_id
    """)
    db.execute(update_branch, {"branch_id": branch_id, "tenant_id": tenant_id_str, "user_name": user_name})
    db.commit()




    return {
        "status": "success",
        "branch_id": branch_id,
        "assigned_user_id": user_id,
        "contact_person_name": user_name,
    }


@router.get("/{branch_id}/programmes")
def get_branch_programmes(
    branch_id: str,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    params = {"tenant_id": str(tenant_id)}

    branch_filter_sql = ""

    if branch_id and branch_id != "ALL":
        try:
            branch_uuid = uuid.UUID(branch_id)
            branch_filter_sql = "AND b.branch_id = :branch_uuid"
            params["branch_uuid"] = branch_uuid
        except ValueError:
            pass

    query = text(f"""
        SELECT DISTINCT
            p.id,
            p.programme_code AS code,
            p.programme_name AS name,
            p.coaching_track,
            COALESCE(p.metadata->>'yearLevel', 'First Year') AS year_level,
            COALESCE(p.metadata->'subjectIds', '[]'::jsonb) AS subject_ids
        FROM sms_batches b
        JOIN sms_academic_programmes p
            ON p.tenant_id = b.tenant_id
            AND p.id = b.programme_id
        WHERE b.tenant_id = :tenant_id
            {branch_filter_sql}
            AND b.status = 'ACTIVE'
            AND p.status = 'ACTIVE'
        ORDER BY p.programme_code
    """)
    rows = db.execute(query, params).fetchall()

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


@router.post("/{branch_id}/programmes")
def assign_branch_programmes(
    branch_id: str,
    payload: dict,
    tenant_id: UUID = Depends(resolve_tenant_id),
    user_id: UUID = Depends(resolve_user_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_uuid = tenant_id
    user_id_uuid = user_id


    try:
        branch_id_uuid = uuid.UUID(branch_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid branch_id UUID",
        ) from exc

    programme_ids = payload.get("programme_ids") or payload.get("programmeIds") or []

    try:
        # Get active default academic year, or create default 2026-2027 if none exists
        ay_res = db.execute(
            text("SELECT id FROM sms_academic_years WHERE tenant_id = :tenant_id AND status = 'ACTIVE' ORDER BY is_default DESC LIMIT 1"),
            {"tenant_id": tenant_id_uuid},
        ).fetchone()

        if not ay_res:
            ay_id_uuid = uuid.uuid4()
            db.execute(
                text("""
                    INSERT INTO sms_academic_years (
                        id, tenant_id, code, name, starts_on, ends_on, status, is_default, created_by, created_at, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, '2026-27', '2026-2027', '2026-06-01', '2027-04-30', 'ACTIVE', true, :user_id, NOW(), NOW()
                    )
                """),
                {"id": ay_id_uuid, "tenant_id": tenant_id_uuid, "user_id": user_id_uuid},
            )
        else:
            ay_id_uuid = ay_res.id

        branch_hex = branch_id_uuid.hex[:4].upper()

        # Collect valid selected programme UUIDs
        selected_prog_uuids = []
        for p_str in programme_ids:
            try:
                selected_prog_uuids.append(uuid.UUID(p_str))
            except ValueError:
                pass

        # Fetch existing batches for this branch and academic year to handle deactivations cleanly
        existing_batches = db.execute(
            text("""
                SELECT id, programme_id, status FROM sms_batches
                WHERE tenant_id = :tenant_id AND branch_id = :branch_id AND academic_year_id = :ay_id
            """),
            {
                "tenant_id": tenant_id_uuid,
                "branch_id": branch_id_uuid,
                "ay_id": ay_id_uuid,
            },
        ).fetchall()

        selected_prog_set = set(selected_prog_uuids)

        # Deactivate batches for programmes that are NOT in user selection (with active enrollment protection)
        for b in existing_batches:
            if b.programme_id not in selected_prog_set and b.status != "INACTIVE":
                student_count = db.execute(
                    text("SELECT COUNT(*) FROM sms_enrollments WHERE batch_id = :batch_id AND status = 'ACTIVE'"),
                    {"batch_id": b.id},
                ).scalar() or 0

                if student_count > 0:
                    prog_info = db.execute(
                        text("SELECT programme_name FROM sms_academic_programmes WHERE id = :id"),
                        {"id": b.programme_id},
                    ).fetchone()
                    prog_name = prog_info.programme_name if prog_info else "Selected stream"
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cannot remove '{prog_name}' offering. {student_count} active students are currently enrolled in this stream for the active academic term.",
                    )

                db.execute(
                    text("UPDATE sms_batches SET status = 'INACTIVE', updated_at = NOW() WHERE id = :id"),
                    {"id": b.id},
                )

        for prog_id_uuid in selected_prog_uuids:
            prog_res = db.execute(
                text("SELECT programme_code, programme_name FROM sms_academic_programmes WHERE id = :prog_id AND tenant_id = :tenant_id"),
                {"prog_id": prog_id_uuid, "tenant_id": tenant_id_uuid},
            ).fetchone()
            if not prog_res:
                continue

            prog_code = prog_res.programme_code
            prog_name = prog_res.programme_name

            for yr_level, yr_name, yr_code in [("1", "First Year", "FY"), ("2", "Second Year", "SY")]:
                batch_code = f"{prog_code}-{branch_hex}-{yr_code}"
                batch_name = f"{prog_code} {yr_name} ({branch_hex})"

                existing_batch = db.execute(
                    text("""
                        SELECT id FROM sms_batches
                        WHERE tenant_id = :tenant_id AND branch_id = :branch_id
                            AND academic_year_id = :ay_id
                            AND (programme_id = :prog_id OR batch_code = :code)
                            AND year_level = :yr_level
                    """),
                    {
                        "tenant_id": tenant_id_uuid,
                        "branch_id": branch_id_uuid,
                        "ay_id": ay_id_uuid,
                        "prog_id": prog_id_uuid,
                        "code": batch_code,
                        "yr_level": yr_level,
                    },
                ).fetchone()

                if existing_batch:
                    batch_id_uuid = existing_batch.id
                    db.execute(
                        text("UPDATE sms_batches SET status = 'ACTIVE', programme_id = :prog_id, updated_at = NOW() WHERE id = :id"),
                        {"id": batch_id_uuid, "prog_id": prog_id_uuid},
                    )
                else:
                    batch_id_uuid = uuid.uuid4()
                    db.execute(
                        text("""
                            INSERT INTO sms_batches (
                                id, tenant_id, branch_id, academic_year_id, programme_id,
                                batch_code, batch_name, year_level, status, created_by, created_at, updated_at
                            )
                            VALUES (
                                :id, :tenant_id, :branch_id, :ay_id, :prog_id,
                                :code, :name, :yr_level, 'ACTIVE', :user_id, NOW(), NOW()
                            )
                        """),
                        {
                            "id": batch_id_uuid,
                            "tenant_id": tenant_id_uuid,
                            "branch_id": branch_id_uuid,
                            "ay_id": ay_id_uuid,
                            "prog_id": prog_id_uuid,
                            "code": batch_code,
                            "name": batch_name,
                            "yr_level": yr_level,
                            "user_id": user_id_uuid,
                        },
                    )

                # Ensure default section A exists for this batch
                sec_code = f"{prog_code}-{yr_level}A-{branch_hex}"
                sec_name = f"{prog_code}-{yr_level}A"
                existing_section = db.execute(
                    text("""
                        SELECT id FROM sms_sections
                        WHERE tenant_id = :tenant_id AND branch_id = :branch_id
                            AND (batch_id = :batch_id OR section_code = :sec_code)
                    """),
                    {
                        "tenant_id": tenant_id_uuid,
                        "branch_id": branch_id_uuid,
                        "batch_id": batch_id_uuid,
                        "sec_code": sec_code,
                    },
                ).fetchone()

                if not existing_section:
                    sec_id_uuid = uuid.uuid4()
                    db.execute(
                        text("""
                            INSERT INTO sms_sections (
                                id, tenant_id, branch_id, batch_id, section_code, section_name,
                                status, created_by, created_at, updated_at
                            )
                            VALUES (
                                :id, :tenant_id, :branch_id, :batch_id, :sec_code, :sec_name,
                                'ACTIVE', :user_id, NOW(), NOW()
                            )
                        """),
                        {
                            "id": sec_id_uuid,
                            "tenant_id": tenant_id_uuid,
                            "branch_id": branch_id_uuid,
                            "batch_id": batch_id_uuid,
                            "sec_code": sec_code,
                            "sec_name": sec_name,
                            "user_id": user_id_uuid,
                        },
                    )

        db.commit()
        return {"status": "success", "message": "Branch programme offerings and batches created successfully."}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign branch programmes: {str(exc)}",
        ) from exc


@router.get("/{branch_id}/sections")
def get_branch_sections(
    branch_id: str,
    exam_id: str | None = None,
    tenant_id: UUID = Depends(resolve_tenant_id),
    db: Session = Depends(get_db_session),
):
    tenant_id_uuid = tenant_id


    try:
        branch_id_uuid = uuid.UUID(branch_id)
    except ValueError:
        return []

    exam_id_uuid = None
    allowed_prog_ids: list[str] = []
    stream_codes: list[str] = []

    if exam_id:
        try:
            exam_id_uuid = uuid.UUID(exam_id)
            exam_row = db.execute(
                text("SELECT programme_id, programme_ids FROM sms_exams WHERE id = :exam_id"),
                {"exam_id": exam_id_uuid},
            ).fetchone()

            if exam_row:
                p_ids = exam_row.programme_ids if isinstance(exam_row.programme_ids, list) else []
                if not p_ids and exam_row.programme_id:
                    p_ids = [str(exam_row.programme_id)]
                allowed_prog_ids = [str(pid) for pid in p_ids if pid]

            if allowed_prog_ids:
                progs = db.execute(
                    text("SELECT programme_code, stream_code FROM sms_academic_programmes WHERE id::text = ANY(CAST(:p_ids AS text[]))"),
                    {"p_ids": allowed_prog_ids},
                ).fetchall()
                for pr in progs:
                    if pr.stream_code:
                        stream_codes.append(pr.stream_code.upper())
                    if pr.programme_code:
                        stream_codes.append(pr.programme_code.upper())
        except ValueError:
            pass

    has_filter = len(allowed_prog_ids) > 0

    query = text("""
        SELECT
            s.id,
            s.section_code AS code,
            s.section_name AS name,
            s.status AS section_status,
            COALESCE(COUNT(DISTINCT e.id), 0) AS student_count,
            COALESCE(COUNT(DISTINCT CASE WHEN r.id IS NOT NULL AND r.subject_marks IS NOT NULL AND r.subject_marks <> '{}'::jsonb THEN r.student_id END), 0) AS entered_count,
            COALESCE(MAX(r.status), 'PENDING') AS exam_status
        FROM sms_sections s
        LEFT JOIN sms_batches b ON b.id = s.batch_id
        LEFT JOIN sms_enrollments e
            ON e.section_id = s.id AND e.status = 'ACTIVE'
        LEFT JOIN sms_student_exam_records r
            ON r.section_id = s.id
            AND r.exam_id = CAST(:exam_id AS uuid)
        WHERE s.tenant_id = :tenant_id
            AND s.branch_id = :branch_id
            AND s.status = 'ACTIVE'
            AND (
                :has_filter = false OR
                (b.programme_id::text = ANY(CAST(:allowed_prog_ids AS text[]))) OR
                (EXISTS (SELECT 1 FROM unnest(CAST(:stream_codes AS text[])) code WHERE s.section_name ILIKE code || '-%' OR s.section_name ILIKE code || '%'))
            )
        GROUP BY s.id, s.section_code, s.section_name, s.status
        ORDER BY s.section_code
    """)

    rows = db.execute(
        query,
        {
            "tenant_id": tenant_id_uuid,
            "branch_id": branch_id_uuid,
            "exam_id": exam_id_uuid,
            "has_filter": has_filter,
            "allowed_prog_ids": allowed_prog_ids if allowed_prog_ids else [""],
            "stream_codes": stream_codes if stream_codes else [""],
        },
    ).fetchall()

    return [
        {
            "id": str(r.id),
            "name": r.name,
            "code": r.code,
            "status": "EXEMPTED" if r.student_count == 0 else (r.exam_status or "PENDING"),
            "studentCount": r.student_count,
            "enteredCount": r.entered_count if r.student_count > 0 else 0,
        }
        for r in rows
    ]
