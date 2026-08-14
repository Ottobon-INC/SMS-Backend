"""Branches module router providing branch endpoints."""

import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

router = APIRouter(prefix="/branches", tags=["branches"])

DEFAULT_TENANT_ID = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"
DEFAULT_USER_ID = "842021d3-9826-4c4f-ad83-504be45d4520"


@router.get("")
@router.get("/")
def get_branches(db: Session = Depends(get_db_session)):
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
    rows = db.execute(query, {"tenant_id": DEFAULT_TENANT_ID}).fetchall()

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
                "contact_person": "Pramod Dean",
                "principalName": "Pramod Dean",
            }
        ]

    return [
        {
            "id": str(r.id),
            "code": r.branch_code,
            "name": r.display_name,
            "branchCode": r.branch_code,
            "displayName": r.display_name,
            "legalName": r.legal_name or r.display_name,
            "legal_name": r.legal_name or r.display_name,
            "status": r.status,
            "address": r.address_data if isinstance(r.address_data, dict) else json.loads(r.address_data or "{}"),
            "contact": r.contact_data if isinstance(r.contact_data, dict) else json.loads(r.contact_data or "{}"),
            "contact_person": "Pramod Dean",
            "principalName": "Pramod Dean",
        }
        for r in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
def create_branch(payload: dict, db: Session = Depends(get_db_session)):
    user_role = payload.get("user_role") or payload.get("role") or ""
    if user_role == "BRANCH_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch creation is restricted to Institution Administrators (Deans). Principals cannot create campus branches.",
        )
    branch_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("branchCode") or payload.get("code") or f"B-{uuid.uuid4().hex[:4].upper()}"
    display_name = payload.get("displayName") or payload.get("name") or "New Campus"
    legal_name = payload.get("legalName") or display_name
    address = payload.get("address") or {}
    contact = payload.get("contact") or {}
    contact_person = payload.get("contactPersonName") or payload.get("contact_person") or "Pramod Dean"

    if isinstance(contact, dict):
        contact["contact_person_name"] = contact_person

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
            "tenant_id": DEFAULT_TENANT_ID,
            "user_id": DEFAULT_USER_ID,
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
def assign_principal(branch_id: str, payload: dict, db: Session = Depends(get_db_session)):
    user_id = payload.get("user_id") or payload.get("principal_user_id")
    user_name = payload.get("user_name") or payload.get("contact_person_name") or "Assigned Principal"

    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")

    deactivate_query = text("""
        UPDATE sms_user_access_assignments
        SET status = 'EXPIRED', valid_until = NOW(), is_primary = false
        WHERE user_id = :user_id AND status = 'ACTIVE' AND is_primary = true
    """)
    db.execute(deactivate_query, {"user_id": user_id})

    assign_id = str(uuid.uuid4())
    insert_query = text("""
        INSERT INTO sms_user_access_assignments (
            id, tenant_id, user_id, role_id, branch_id, scope_type, is_primary, status, valid_from, created_at, updated_at
        )
        SELECT
            :id, :tenant_id, :user_id, r.id, :branch_id, 'BRANCH', true, 'ACTIVE', NOW(), NOW(), NOW()
        FROM sms_roles r
        WHERE r.role_code = 'BRANCH_ADMIN'
        LIMIT 1
    """)
    db.execute(
        insert_query,
        {
            "id": assign_id,
            "tenant_id": DEFAULT_TENANT_ID,
            "user_id": user_id,
            "branch_id": branch_id,
        },
    )

    update_branch = text("""
        UPDATE sms_branches
        SET contact_data = jsonb_set(
            COALESCE(contact_data, '{}'::jsonb),
            '{contact_person_name}',
            to_jsonb(:user_name::text)
        ),
        updated_at = NOW()
        WHERE id = :branch_id AND tenant_id = :tenant_id
    """)
    db.execute(update_branch, {"branch_id": branch_id, "tenant_id": DEFAULT_TENANT_ID, "user_name": user_name})
    db.commit()

    return {
        "status": "success",
        "branch_id": branch_id,
        "assigned_user_id": user_id,
        "contact_person_name": user_name,
    }
