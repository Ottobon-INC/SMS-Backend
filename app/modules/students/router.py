import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database.session import get_db_session

router = APIRouter(prefix="/students", tags=["students"])

@router.get("")
@router.get("/")
def get_students(branch_id: str | None = None, db: Session = Depends(get_db_session)):
    query = text("SELECT id, student_number, display_name, gender, current_status FROM sms_students WHERE current_status = 'ACTIVE'")
    rows = db.execute(query).fetchall()
    if not rows:
        return [
          {"id": "stu-101", "admissionNumber": "SVIC-2026-001", "name": "Aarav Sharma", "rollNo": "101", "gender": "MALE", "stream": "MPC", "section": "Sec-A", "status": "ACTIVE"},
          {"id": "stu-102", "admissionNumber": "SVIC-2026-002", "name": "Ananya Verma", "rollNo": "102", "gender": "FEMALE", "stream": "MPC", "section": "Sec-A", "status": "ACTIVE"},
          {"id": "stu-103", "admissionNumber": "SVIC-2026-003", "name": "Rohan Reddy", "rollNo": "103", "gender": "MALE", "stream": "BiPC", "section": "Sec-B", "status": "ACTIVE"},
        ]
    return [{"id": str(r.id), "admissionNumber": r.student_number or "SVIC-2026-001", "name": r.display_name, "rollNo": "101", "gender": r.gender or "MALE", "stream": "MPC", "section": "Sec-A", "status": r.current_status} for r in rows]

@router.post("")
@router.post("/")
def create_student(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = "00000000-0000-0000-0000-000000000001"
    student_id = payload.get("id") or str(uuid.uuid4())
    student_number = payload.get("admissionNumber") or f"SVIC-2026-{uuid.uuid4().hex[:4].upper()}"
    display_name = payload.get("name") or "New Student"
    gender = payload.get("gender") or "MALE"
    
    query = text("""
        INSERT INTO sms_students (id, tenant_id, student_number, display_name, legal_name, gender, current_status, created_at, updated_at)
        VALUES (:id, :tenant_id, :student_number, :display_name, :legal_name, :gender, 'ACTIVE', NOW(), NOW())
        RETURNING id, student_number, display_name, gender, current_status
    """)
    res = db.execute(query, {
        "id": student_id,
        "tenant_id": tenant_id,
        "student_number": student_number,
        "display_name": display_name,
        "legal_name": display_name,
        "gender": gender,
    }).fetchone()
    db.commit()
    return {
        "id": str(res.id),
        "admissionNumber": res.student_number,
        "name": res.display_name,
        "rollNo": "104",
        "gender": res.gender,
        "stream": payload.get("stream") or "MPC",
        "section": "Sec-A",
        "status": res.current_status,
    }
