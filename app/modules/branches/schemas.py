
from pydantic import BaseModel, Field


class AddressDataSchema(BaseModel):
    street: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = "Telangana"
    pincode: str | None = None

class ContactDataSchema(BaseModel):
    primary_phone: str | None = None
    email: str | None = None
    contact_person_name: str | None = None
    contact_person_role: str | None = "Campus Director"

class BranchCreatePayload(BaseModel):
    code: str = Field(..., description="Unique branch code, e.g. HYD-MAIN")
    name: str = Field(..., description="Display name of campus")
    legal_name: str | None = None
    status: str | None = "DRAFT"
    timezone: str | None = "Asia/Kolkata"
    address: AddressDataSchema | None = None
    contact: ContactDataSchema | None = None
    principal_user_id: str | None = None

class BranchResponse(BaseModel):
    id: str
    code: str
    name: str
    legal_name: str | None = None
    status: str
    timezone: str
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    contact_person: str | None = None
    address_data: dict[str, object] | None = None
    contact_data: dict[str, object] | None = None
