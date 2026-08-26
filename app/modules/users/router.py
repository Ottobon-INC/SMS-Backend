# mypy: ignore-errors
# ruff: noqa: B008, E501
"""Users module router.

Responsibilities for this layer are documented in the architecture docs.
"""

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

from uuid import UUID
from app.core.security.context import RequestContext
from app.core.security.dependencies import require_permission

router = APIRouter(prefix="/users", tags=["users"])

USER_VIEW = "user.view"
USER_CREATE = "user.create"


def _require_tenant_context(context: RequestContext) -> UUID:
    if context.tenant_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant scope required.")
    return context.tenant_id


@router.get("")
@router.get("/")
def get_users(
    context: RequestContext = Depends(require_permission(USER_VIEW)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
    params: dict[str, object] = {"tenant_id": tenant_id}
    branch_filter_sql = ""
    if context.branch_id is not None:
        branch_filter_sql = "AND a.branch_id = :branch_id"
        params["branch_id"] = context.branch_id

    query = text("""
        SELECT DISTINCT ON (LOWER(u.email))
            u.id,
            u.full_name,
            u.email,
            u.mobile,
            u.account_category,
            u.status,
            COALESCE(r.role_code, u.account_category) AS role,
            CASE
                WHEN a.scope_type = 'PLATFORM' THEN 'Platform'
                WHEN a.scope_type = 'TENANT' THEN COALESCE(t.display_name, 'All Campuses')
                WHEN a.scope_type = 'BRANCH' THEN COALESCE(b.display_name, 'Assigned Campus')
                ELSE 'Unassigned'
            END AS branch
        FROM sms_users u
        LEFT JOIN LATERAL (
            SELECT
                a.role_id,
                a.scope_type,
                a.tenant_id,
                a.branch_id,
                a.is_primary
            FROM sms_user_access_assignments a
            WHERE
                a.user_id = u.id
                AND a.status = 'ACTIVE'
                AND a.valid_from <= NOW()
                AND (a.valid_until IS NULL OR a.valid_until > NOW())
            ORDER BY a.is_primary DESC, a.created_at DESC
            LIMIT 1
        ) a ON TRUE
        LEFT JOIN sms_roles r ON r.id = a.role_id
        LEFT JOIN sms_tenants t ON t.id = a.tenant_id
        LEFT JOIN sms_branches b ON b.tenant_id = a.tenant_id AND b.id = a.branch_id
        WHERE u.status = 'ACTIVE'
            AND u.tenant_id = :tenant_id
            """ + branch_filter_sql + """
        ORDER BY LOWER(u.email), u.created_at DESC
    """)

    rows = db.execute(query, params).fetchall()
    return [
        {
            "id": str(r.id),
            "name": r.full_name,
            "email": r.email or "user@svic.edu",
            "mobile": r.mobile or "+91 98765 00000",
            "role": r.role or "UNASSIGNED",
            "branch": r.branch or "Unassigned",
            "status": r.status,
        }
        for r in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: dict,
    context: RequestContext = Depends(require_permission(USER_CREATE)),
    db: Session = Depends(get_db_session),
):
    tenant_id = _require_tenant_context(context)
    assigned_by = context.app_user_id
    target_role = payload.get("role") or "OFFICE_STAFF"
    if context.branch_id is not None and target_role != "OFFICE_STAFF":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch-scoped users can create only office staff accounts for their campus.",
        )
    if target_role == "INSTITUTION_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creation of Dean (Institution Admin) accounts is restricted to Platform Super Administrators.",
        )

    user_id = payload.get("id") or str(_uuid.uuid4())
    full_name = payload.get("name") or "New User"
    email = payload.get("email") or f"user.{_uuid.uuid4().hex[:4]}@svic.edu"
    mobile = payload.get("mobile") or "+91 98765 43210"

    tenant_id_str = str(tenant_id)
    user_query = text("""
        INSERT INTO sms_users (id, tenant_id, account_category, full_name, email, mobile, status, created_at, updated_at)
        VALUES (:id, :tenant_id, 'TENANT', :full_name, :email, :mobile, 'ACTIVE', NOW(), NOW())
        ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name, updated_at = NOW()
        RETURNING id, full_name, email, mobile, status
    """)
    res = db.execute(
        user_query,
        {
            "id": user_id,
            "tenant_id": tenant_id_str,
            "full_name": full_name,
            "email": email,
            "mobile": mobile,
        },
    ).fetchone()

    is_branch_scoped = target_role in ("BRANCH_ADMIN", "OFFICE_STAFF")
    branch_id = str(context.branch_id) if context.branch_id is not None else payload.get("branch_id")
    if not branch_id and is_branch_scoped:
        first_branch = db.execute(text("SELECT id FROM sms_branches WHERE tenant_id = :tenant_id AND status = 'ACTIVE' LIMIT 1"), {"tenant_id": tenant_id_str}).scalar_one_or_none()
        branch_id = str(first_branch) if first_branch else None

    scope_type = "BRANCH" if is_branch_scoped else "TENANT"

    role_lookup = db.execute(
        text("SELECT id FROM sms_roles WHERE role_code = :role_code LIMIT 1"),
        {"role_code": target_role},
    ).fetchone()
    role_id = str(role_lookup.id) if role_lookup else None

    if role_id:
        assignment_query = text("""
            INSERT INTO sms_user_access_assignments (
                id, tenant_id, user_id, role_id, branch_id, scope_type,
                is_primary, status, valid_from, assigned_by, created_at, updated_at
            )
            VALUES (
                :id, :tenant_id, :user_id, :role_id, :branch_id, :scope_type,
                true, 'ACTIVE', NOW(), :assigned_by, NOW(), NOW()
            )
            ON CONFLICT DO NOTHING
        """)
        db.execute(
            assignment_query,
            {
                "id": str(_uuid.uuid4()),
                "tenant_id": tenant_id_str,
                "user_id": str(res.id),
                "role_id": role_id,
                "branch_id": branch_id,
                "scope_type": scope_type,
                "assigned_by": str(assigned_by),
            },
        )


    db.commit()

    return {
        "id": str(res.id),
        "name": res.full_name,
        "email": res.email,
        "mobile": res.mobile,
        "role": target_role,
        "branch": payload.get("branch") or "Main Campus",
        "status": res.status,
    }
