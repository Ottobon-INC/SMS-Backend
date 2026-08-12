import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.database.session import get_db_session
from app.modules.branches.schemas import BranchCreatePayload, BranchResponse

router = APIRouter(prefix="/branches", tags=["branches"])

@router.get("", response_model=list[BranchResponse])
@router.get("/", response_model=list[BranchResponse])
def get_branches(db: Session = Depends(get_db_session)):
    query = text("""
        SELECT 
            id, 
            branch_code as code, 
            display_name as name, 
            legal_name,
            status,
            timezone,
            address_data,
            contact_data
        FROM sms_branches 
        WHERE status != 'CLOSED'
        ORDER BY created_at DESC
    """)
    rows = db.execute(query).fetchall()
    
    result = []
    for r in rows:
        addr_dict = r.address_data if isinstance(r.address_data, dict) else (json.loads(r.address_data) if r.address_data else {})
        cont_dict = r.contact_data if isinstance(r.contact_data, dict) else (json.loads(r.contact_data) if r.contact_data else {})
        
        street = addr_dict.get('street', '')
        city = addr_dict.get('city', '')
        state = addr_dict.get('state', 'Telangana')
        formatted_address = f"{street}, {city}, {state}".strip(', ') if (street or city) else "Hyderabad Campus, Telangana"
        
        result.append(BranchResponse(
            id=str(r.id),
            code=r.code,
            name=r.name,
            legal_name=r.legal_name,
            status=r.status,
            timezone=r.timezone or "Asia/Kolkata",
            phone=cont_dict.get('primary_phone') or "+91 98765 43210",
            email=cont_dict.get('email') or "branch@svic.edu",
            address=formatted_address,
            contact_person=cont_dict.get('contact_person_name') or "Campus Director",
            address_data=addr_dict,
            contact_data=cont_dict
        ))
    return result

@router.post("", response_model=BranchResponse)
@router.post("/", response_model=BranchResponse)
def create_branch(payload: BranchCreatePayload, db: Session = Depends(get_db_session)):
    tenant_id = "00000000-0000-0000-0000-000000000001"
    branch_id = str(uuid.uuid4())
    
    address_json = json.dumps(payload.address.model_dump() if payload.address else {"state": "Telangana"})
    contact_json = json.dumps(payload.contact.model_dump() if payload.contact else {"contact_person_role": "Campus Director"})
    
    query = text("""
        INSERT INTO sms_branches (
            id, tenant_id, branch_code, display_name, legal_name, status, timezone, address_data, contact_data, created_at, updated_at
        )
        VALUES (
            :id, :tenant_id, :code, :name, :legal_name, :status, :timezone, CAST(:address_data AS jsonb), CAST(:contact_data AS jsonb), NOW(), NOW()
        )
        RETURNING id, branch_code as code, display_name as name, legal_name, status, timezone, address_data, contact_data
    """)
    
    res = db.execute(query, {
        "id": branch_id,
        "tenant_id": tenant_id,
        "code": payload.code,
        "name": payload.name,
        "legal_name": payload.legal_name or f"{payload.name} Legal Entity",
        "status": payload.status or "DRAFT",
        "timezone": payload.timezone or "Asia/Kolkata",
        "address_data": address_json,
        "contact_data": contact_json,
    }).fetchone()
    db.commit()
    
    addr_dict = res.address_data if isinstance(res.address_data, dict) else (json.loads(res.address_data) if res.address_data else {})
    cont_dict = res.contact_data if isinstance(res.contact_data, dict) else (json.loads(res.contact_data) if res.contact_data else {})
    
    return BranchResponse(
        id=str(res.id),
        code=res.code,
        name=res.name,
        legal_name=res.legal_name,
        status=res.status,
        timezone=res.timezone,
        phone=cont_dict.get('primary_phone'),
        email=cont_dict.get('email'),
        address=f"{addr_dict.get('street', '')}, {addr_dict.get('city', '')}".strip(', '),
        contact_person=cont_dict.get('contact_person_name'),
        address_data=addr_dict,
        contact_data=cont_dict
    )
