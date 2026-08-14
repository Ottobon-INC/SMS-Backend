
from pydantic import BaseModel, Field


class StudentAddressSchema(BaseModel):
    street: str | None = None
    city: str | None = None
    pincode: str | None = None

class GuardianDataSchema(BaseModel):
    father_name: str | None = None
    mother_name: str | None = None
    guardian_phone: str | None = None
    guardian_email: str | None = None

class StudentCreatePayload(BaseModel):
    name: str = Field(..., description="Student full name")
    admissionNumber: str | None = None
    gender: str | None = "MALE"
    date_of_birth: str | None = None
    blood_group: str | None = None
    stream: str | None = "MPC"
    section: str | None = "Sec-A"
    address: StudentAddressSchema | None = None
    guardian: GuardianDataSchema | None = None

class StudentResponse(BaseModel):
    id: str
    admissionNumber: str
    name: str
    rollNo: str
    gender: str
    stream: str
    section: str
    status: str
    father_name: str | None = None
    guardian_phone: str | None = None
    address_data: dict[str, object] | None = None
    guardian_data: dict[str, object] | None = None
