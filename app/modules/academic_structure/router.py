import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database.session import get_db_session

router = APIRouter(prefix="/academic-structure", tags=["academic_structure"])

@router.get("/subjects")
def get_subjects(db: Session = Depends(get_db_session)):
    query = text("SELECT id, subject_code as code, subject_name as name, 100 as max_marks, 35 as pass_marks FROM sms_subjects WHERE status = 'ACTIVE'")
    rows = db.execute(query).fetchall()
    return [{"id": str(r.id), "code": r.code, "name": r.name, "maxMarks": r.max_marks, "passMarks": r.pass_marks} for r in rows]

@router.post("/subjects")
def create_subject(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"
    sub_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or "SUB-101"
    name = payload.get("name") or "New Subject"
    
    query = text("""
        INSERT INTO sms_subjects (id, tenant_id, subject_code, subject_name, status, created_by, created_at, updated_at)
        VALUES (:id, :tenant_id, :code, :name, 'ACTIVE', :created_by, NOW(), NOW())
        RETURNING id, subject_code as code, subject_name as name
    """)
    res = db.execute(query, {"id": sub_id, "tenant_id": tenant_id, "code": code, "name": name, "created_by": user_id}).fetchone()
    db.commit()
    return {"id": str(res.id), "code": res.code, "name": res.name, "maxMarks": 100, "passMarks": 35}

@router.get("/programmes")
def get_programmes(db: Session = Depends(get_db_session)):
    query = text("SELECT id, programme_code as code, programme_name as name FROM sms_academic_programmes WHERE status = 'ACTIVE'")
    rows = db.execute(query).fetchall()
    return [{"id": str(r.id), "code": r.code, "name": r.name, "yearLevel": "First Year"} for r in rows]

@router.post("/programmes")
def create_programme(payload: dict, db: Session = Depends(get_db_session)):
    tenant_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000002"
    prog_id = payload.get("id") or str(uuid.uuid4())
    code = payload.get("code") or "STREAM"
    name = payload.get("name") or "Course Stream"
    
    query = text("""
        INSERT INTO sms_academic_programmes (id, tenant_id, programme_code, programme_name, status, created_by, created_at, updated_at)
        VALUES (:id, :tenant_id, :code, :name, 'ACTIVE', :created_by, NOW(), NOW())
        RETURNING id, programme_code as code, programme_name as name
    """)
    res = db.execute(query, {"id": prog_id, "tenant_id": tenant_id, "code": code, "name": name, "created_by": user_id}).fetchone()
    db.commit()
    return {"id": str(res.id), "code": res.code, "name": res.name, "yearLevel": "First Year"}
