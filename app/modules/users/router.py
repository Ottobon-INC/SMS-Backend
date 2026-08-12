import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database.session import get_db_session

router = APIRouter(prefix="/users", tags=["users"])

@router.get("")
@router.get("/")
def get_users(db: Session = Depends(get_db_session)):
    query = text("SELECT id, full_name, email, mobile, account_category, status FROM sms_users WHERE status = 'ACTIVE'")
    rows = db.execute(query).fetchall()
    if not rows:
        return [
          {"id": "usr-101", "name": "Pramod Dean", "email": "dean@svic.edu", "mobile": "+91 98765 00001", "role": "INSTITUTION_ADMIN", "branch": "All Campuses", "status": "ACTIVE"},
          {"id": "usr-102", "name": "Dr. K. V. Rao", "email": "principal.hyd@svic.edu", "mobile": "+91 98765 00002", "role": "BRANCH_ADMIN", "branch": "Hyderabad Main Campus", "status": "ACTIVE"},
          {"id": "usr-103", "name": "Sita Lakshmi", "email": "maths.teacher@svic.edu", "mobile": "+91 98765 00003", "role": "TEACHER", "branch": "Hyderabad Main Campus", "status": "ACTIVE"},
        ]
    return [{"id": str(r.id), "name": r.full_name, "email": r.email or "user@svic.edu", "mobile": r.mobile or "+91 98765 00000", "role": "BRANCH_ADMIN", "branch": "Hyderabad Main Campus", "status": r.status} for r in rows]

@router.post("")
@router.post("/")
def create_user(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = "00000000-0000-0000-0000-000000000001"
    user_id = payload.get("id") or str(uuid.uuid4())
    full_name = payload.get("name") or "New User"
    email = payload.get("email") or f"user.{uuid.uuid4().hex[:4]}@svic.edu"
    mobile = payload.get("mobile") or "+91 98765 43210"
    
    query = text("""
        INSERT INTO sms_users (id, tenant_id, account_category, full_name, email, mobile, status, created_at, updated_at)
        VALUES (:id, :tenant_id, 'TENANT', :full_name, :email, :mobile, 'ACTIVE', NOW(), NOW())
        RETURNING id, full_name, email, mobile, status
    """)
    res = db.execute(query, {
        "id": user_id,
        "tenant_id": tenant_id,
        "full_name": full_name,
        "email": email,
        "mobile": mobile,
    }).fetchone()
    db.commit()
    return {
        "id": str(res.id),
        "name": res.full_name,
        "email": res.email,
        "mobile": res.mobile,
        "role": payload.get("role") or "BRANCH_ADMIN",
        "branch": payload.get("branch") or "Hyderabad Main Campus",
        "status": res.status,
    }
