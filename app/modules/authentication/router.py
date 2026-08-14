"""Authentication module router providing login and user context endpoints."""

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session

router = APIRouter(prefix="/auth", tags=["authentication"])

DEFAULT_TENANT_ID = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"
DEFAULT_BRANCH_ID = "8854ab2a-44cf-4770-bb51-5f78e0876e9d"

ALL_ENABLED_MODULES = [
    "dashboard",
    "branches",
    "students",
    "users",
    "institution",
    "academic-structure",
    "examinations",
    "attendance",
    "fees",
    "imports",
    "reports",
    "notifications",
    "audit",
    "support",
    "parent-portal",
    "platform-admin",
]

ALL_PERMISSIONS = [
    "dashboard.view",
    "branch.view",
    "branch.manage",
    "student.view",
    "student.create",
    "student.edit",
    "user.view",
    "user.manage",
    "institution.view",
    "academic_structure.view",
    "exam.view",
    "exam.create",
    "attendance.view",
    "fee.view",
    "import.view",
    "report.branch_view",
    "notification.view",
    "audit.view",
    "parent.child_view",
]


class LoginPayload(BaseModel):
    login_identifier: str
    password: str
    portal: Optional[str] = "branch"


SESSION_USER_MAP: Dict[str, Any] = {}
SESSION_PORTAL_MAP: Dict[str, str] = {}


def build_user_context(user_row: Any = None, portal: str = "branch") -> Dict[str, Any]:
    assignment_id = f"assign-{portal}-101"

    if portal == "institution":
        role_code = "INSTITUTION_ADMIN"
        role_label = "Dean / Institution Admin"
        scope_type = "TENANT"
        default_name = "Pramod Dean"
        default_email = "pramod@dean.com"
        branch_id = None
        user_id = "842021d3-9826-4c4f-ad83-504be45d4510"
    elif portal == "office":
        role_code = "OFFICE_STAFF"
        role_label = "Office Staff"
        scope_type = "BRANCH"
        default_name = "Pramod Office Staff"
        default_email = "pramod@office.com"
        branch_id = DEFAULT_BRANCH_ID
        user_id = "842021d3-9826-4c4f-ad83-504be45d4530"
    elif portal == "parent":
        role_code = "PARENT_GUARDIAN"
        role_label = "Parent / Guardian"
        scope_type = "SELF"
        default_name = "Pramod Parent"
        default_email = "pramod@parent.com"
        branch_id = DEFAULT_BRANCH_ID
        user_id = "842021d3-9826-4c4f-ad83-504be45d4540"
    else:  # branch (Principal)
        role_code = "BRANCH_ADMIN"
        role_label = "Principal / Campus Admin"
        scope_type = "BRANCH"
        default_name = "Pramod Principal"
        default_email = "pramod@principal.com"
        branch_id = DEFAULT_BRANCH_ID
        user_id = "842021d3-9826-4c4f-ad83-504be45d4520"

    if user_row and hasattr(user_row, "id"):
        user_id = str(user_row.id)

    full_name = getattr(user_row, "full_name", default_name) if user_row else default_name
    email = getattr(user_row, "email", default_email) if user_row else default_email
    account_category = getattr(user_row, "account_category", "TENANT") if user_row else "TENANT"

    # --- Role-based module and permission filtering ---
    OFFICE_STAFF_MODULES = ["dashboard", "academic-structure", "students", "imports", "fees", "attendance", "examinations", "reports", "notifications"]
    PARENT_MODULES = ["parent-portal", "notifications"]
    OFFICE_STAFF_PERMISSIONS = ["dashboard.view", "academic_structure.view", "student.view", "student.create", "student.edit", "import.view", "fee.view", "attendance.view", "exam.view", "report.branch_view", "notification.view"]
    PARENT_PERMISSIONS = ["parent.child_view", "notification.view"]

    if role_code == "OFFICE_STAFF":
        enabled_modules = OFFICE_STAFF_MODULES
        permissions = OFFICE_STAFF_PERMISSIONS
    elif role_code == "PARENT_GUARDIAN":
        enabled_modules = PARENT_MODULES
        permissions = PARENT_PERMISSIONS
    elif role_code == "BRANCH_ADMIN":
        # Principal: all except branches module itself
        enabled_modules = [m for m in ALL_ENABLED_MODULES if m != "branches"]
        permissions = [p for p in ALL_PERMISSIONS if p not in ["branch.view", "branch.create", "branch.manage", "branch.update"]]
        permissions.extend(["user.view", "user.manage"])
    else:  # INSTITUTION_ADMIN / PLATFORM_ADMIN — full access
        enabled_modules = ALL_ENABLED_MODULES
        permissions = list(ALL_PERMISSIONS) + ["branch.manage", "branch.create", "branch.view", "user.view", "user.manage"]

    context_summary = {
        "assignment_id": assignment_id,
        "tenant": {
            "id": DEFAULT_TENANT_ID,
            "name": "Development College",
            "status": "ACTIVE",
        },
        "branch": {
            "id": DEFAULT_BRANCH_ID,
            "name": "Main Campus",
            "status": "ACTIVE",
        } if branch_id else None,
        "role": {
            "code": role_code,
            "label": role_label,
        },
        "scope_type": scope_type,
        "enabled_modules": enabled_modules,
        "permissions": permissions,
    }

    active_context = {
        "assignment_id": assignment_id,
        "tenant_id": DEFAULT_TENANT_ID,
        "branch_id": branch_id,
        "role_codes": [role_code],
        "scope_type": scope_type,
        "enabled_modules": enabled_modules,
        "permissions": permissions,
    }

    return {
        "user": {
            "id": user_id,
            "display_name": full_name,
            "email": email,
            "status": "ACTIVE",
            "account_category": account_category,
        },
        "available_contexts": [context_summary],
        "active_context": active_context,
    }


@router.post("/login")
def login(payload: LoginPayload, db: Session = Depends(get_db_session)):
    user_row = None
    try:
        query = text("""
            SELECT id, full_name, email, account_category, status
            FROM sms_users
            WHERE (email = :identifier OR mobile = :identifier OR lower(full_name) LIKE lower(:like_id)) AND status = 'ACTIVE'
            LIMIT 1
        """)
        user_row = db.execute(
            query,
            {
                "identifier": payload.login_identifier,
                "like_id": f"%{payload.login_identifier}%",
            },
        ).fetchone()
    except Exception:
        user_row = None

    portal = payload.portal or "branch"
    identifier_lower = (payload.login_identifier or "").lower()
    if "office" in identifier_lower:
        portal = "office"
    elif "dean" in identifier_lower:
        portal = "institution"
    elif "principal" in identifier_lower:
        portal = "branch"
    base_context = build_user_context(user_row, portal=portal)
    token = f"dev_token_{uuid.uuid4().hex[:12]}"
    SESSION_PORTAL_MAP[token] = portal
    assignment_id = f"assign-{portal}-101"
    SESSION_PORTAL_MAP[assignment_id] = portal

    if user_row:
        SESSION_USER_MAP[token] = user_row
        SESSION_USER_MAP[assignment_id] = user_row

    base_context.update(
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in_seconds": 86400,
        }
    )
    return base_context


@router.get("/me")
def get_current_user(
    db: Session = Depends(get_db_session),
    authorization: Optional[str] = Header(None),
    x_assignment_id: Optional[str] = Header(None, alias="X-Access-Assignment-ID"),
):
    token = (authorization or "").replace("Bearer ", "").strip()
    portal = (
        SESSION_PORTAL_MAP.get(x_assignment_id or "")
        or SESSION_PORTAL_MAP.get(token)
        or ("institution" if x_assignment_id == "assign-institution-101" else "branch")
    )
    user_row = SESSION_USER_MAP.get(token) or SESSION_USER_MAP.get(x_assignment_id or "")

    return build_user_context(user_row, portal=portal)


@router.post("/select-context")
def select_context(
    payload: dict,
    db: Session = Depends(get_db_session),
    authorization: Optional[str] = Header(None),
    x_assignment_id: Optional[str] = Header(None, alias="X-Access-Assignment-ID"),
):
    token = (authorization or "").replace("Bearer ", "").strip()
    target_id = payload.get("assignment_id") or x_assignment_id or ""
    portal = (
        SESSION_PORTAL_MAP.get(target_id)
        or SESSION_PORTAL_MAP.get(token)
        or ("institution" if target_id == "assign-institution-101" else "branch")
    )
    user_row = SESSION_USER_MAP.get(token) or SESSION_USER_MAP.get(target_id)

    return build_user_context(user_row, portal=portal)


@router.post("/signup-request")
def signup_request(payload: dict):
    return {
        "request_id": str(uuid.uuid4()),
        "status": "PENDING_APPROVAL",
    }
