from pydantic import BaseModel, Field
from typing import Optional

class AddressDataSchema(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = "Telangana"
    pincode: Optional[str] = None

class ContactDataSchema(BaseModel):
    primary_phone: Optional[str] = None
    email: Optional[str] = None
    contact_person_name: Optional[str] = None
    contact_person_role: Optional[str] = "Campus Director"

class BranchCreatePayload(BaseModel):
    code: str = Field(..., description="Unique branch code, e.g. HYD-MAIN")
    name: str = Field(..., description="Display name of campus")
    legal_name: Optional[str] = None
    status: Optional[str] = "DRAFT"
    timezone: Optional[str] = "Asia/Kolkata"
    address: Optional[AddressDataSchema] = None
    contact: Optional[ContactDataSchema] = None
    principal_user_id: Optional[str] = None

class BranchResponse(BaseModel):
    id: str
    code: str
    name: str
    legal_name: Optional[str] = None
    status: str
    timezone: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    address_data: Optional[dict] = None
    contact_data: Optional[dict] = None
