import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database.session import get_db_session

router = APIRouter(prefix="/students", tags=["students"])

@router.get("")
@router.get("/")
def get_students(branch_id: str | None = None, db: Session = Depends(get_db_session)):
    query_str = """
        SELECT 
            s.id, 
            s.student_number, 
            e.admission_number,
            s.display_name, 
            s.gender, 
            s.current_status,
            e.roll_number,
            p.programme_name as stream,
            sec.section_name as section,
            g.full_name as guardian_name,
            sgl.relationship_type as guardian_relationship,
            g.mobile as guardian_phone
        FROM sms_students s
        LEFT JOIN sms_enrollments e ON e.student_id = s.id AND e.is_current = true
        LEFT JOIN sms_academic_programmes p ON p.id = e.programme_id
        LEFT JOIN sms_sections sec ON sec.id = e.section_id
        LEFT JOIN sms_student_guardian_links sgl ON sgl.student_id = s.id AND sgl.is_primary = true
        LEFT JOIN sms_guardians g ON g.id = sgl.guardian_id
        WHERE s.current_status = 'ACTIVE'
    """
    
    if branch_id:
        query_str += f" AND e.branch_id = '{branch_id}'"
        
    query_str += " ORDER BY s.created_at DESC"
        
    rows = db.execute(text(query_str)).fetchall()
    
    if not rows:
        return []
        
    return [{
        "id": str(r.id), 
        "admissionNumber": r.admission_number or r.student_number or "N/A", 
        "name": r.display_name, 
        "rollNo": r.roll_number or "-", 
        "gender": r.gender or "-", 
        "stream": r.stream or "-", 
        "section": r.section or "-", 
        "status": r.current_status,
        "father_name": r.guardian_name or "N/A",
        "guardian_relationship": r.guardian_relationship or "GUARDIAN",
        "guardian_phone": r.guardian_phone or "N/A"
    } for r in rows]

@router.post("")
@router.post("/")
def create_student(payload: dict, db: Session = Depends(get_db_session)):
    # Dynamically fetch the first tenant for this test endpoint
    tenant_id_row = db.execute(text("SELECT id FROM sms_tenants LIMIT 1")).fetchone()
    tenant_id = str(tenant_id_row[0]) if tenant_id_row else "00000000-0000-0000-0000-000000000001"
    
    # Dynamically fetch the first user for this test endpoint to satisfy created_by
    user_id_row = db.execute(text("SELECT id FROM sms_users LIMIT 1")).fetchone()
    app_user_id = str(user_id_row[0]) if user_id_row else "00000000-0000-0000-0000-000000000001"
    
    student_id = payload.get("id") or str(uuid.uuid4())
    student_number = payload.get("admissionNumber") or f"SVIC-2026-{uuid.uuid4().hex[:4].upper()}"
    display_name = payload.get("name") or "New Student"
    gender = payload.get("gender") or "MALE"
    date_of_birth = payload.get("date_of_birth") or "2010-01-01"
    
    query = text("""
        INSERT INTO sms_students (id, tenant_id, student_number, display_name, legal_name, gender, date_of_birth, source_type, created_by, current_status, created_at, updated_at)
        VALUES (:id, :tenant_id, :student_number, :display_name, :legal_name, :gender, :date_of_birth, 'MANUAL', :app_user_id, 'ACTIVE', NOW(), NOW())
        RETURNING id, student_number, display_name, gender, current_status
    """)
    try:
        res = db.execute(query, {
            "id": student_id,
            "tenant_id": tenant_id,
            "student_number": student_number,
            "display_name": display_name,
            "legal_name": display_name,
            "gender": gender,
            "date_of_birth": date_of_birth,
            "app_user_id": app_user_id,
        }).fetchone()
        
        if not res:
            raise Exception("Failed to insert student")
            
        db.commit()
        return {
            "id": str(res.id),
            "admissionNumber": res.student_number,
            "name": res.display_name,
            "rollNo": "101",
            "gender": res.gender,
            "stream": "MPC",
            "section": "Sec-A",
            "status": res.current_status
        }
    except Exception as e:
        from fastapi import Response
        return Response(content=str(e), status_code=500)
