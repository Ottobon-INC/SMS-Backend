from pydantic import BaseModel, Field
from typing import Optional

class StudentAddressSchema(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    pincode: Optional[str] = None

class GuardianDataSchema(BaseModel):
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_email: Optional[str] = None

class StudentCreatePayload(BaseModel):
    name: str = Field(..., description="Student full name")
    admissionNumber: Optional[str] = None
    gender: Optional[str] = "MALE"
    date_of_birth: Optional[str] = None
    blood_group: Optional[str] = None
    stream: Optional[str] = "MPC"
    section: Optional[str] = "Sec-A"
    address: Optional[StudentAddressSchema] = None
    guardian: Optional[GuardianDataSchema] = None

class StudentResponse(BaseModel):
    id: str
    admissionNumber: str
    name: str
    rollNo: str
    gender: str
    stream: str
    section: str
    status: str
    father_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    address_data: Optional[dict] = None
    guardian_data: Optional[dict] = None
