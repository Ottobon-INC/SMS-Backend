# ruff: noqa: E501

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ImportBatchResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: UUID | None
    module_code: str
    import_type: str
    schema_version: str
    source_filename: str
    status: str
    summary: dict[str, Any] | None
    created_at: datetime
    submitted_at: datetime | None
    approved_at: datetime | None
    committed_at: datetime | None

    class Config:
        from_attributes = True


class ImportRowResult(BaseModel):
    id: UUID
    batch_id: UUID
    row_number: int
    raw_data: dict[str, Any] | None
    normalized_data: dict[str, Any] | None
    validation_status: str
    errors: list[dict[str, Any]]
    proposed_action: str | None
    target_entity_type: str | None
    target_entity_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class PreviewResponse(BaseModel):
    batch: ImportBatchResponse
    rows: list[ImportRowResult]


class CommitResponse(BaseModel):
    message: str
    batch: ImportBatchResponse


class UploadResponse(BaseModel):
    message: str
    batch_id: UUID
    status: str


class ManualAddStudentRequest(BaseModel):
    student_name: str = Field(..., min_length=1, max_length=200)
    date_of_birth: date
    gender: str = Field(..., pattern="^(MALE|FEMALE|OTHER)$")
    
    admission_number: str = Field(..., min_length=1, max_length=60)
    branch_id: UUID
    academic_year_id: UUID
    programme_id: UUID
    batch_id: UUID
    section_id: UUID
    year_level: str = Field(..., pattern="^(FIRST_YEAR|SECOND_YEAR|First Year|Second Year)$")
    roll_number: str | None = Field(default=None, max_length=60)
    
    guardian_name: str = Field(..., min_length=1, max_length=200)
    guardian_mobile: str = Field(..., pattern=r"^\+?[0-9\-\s]+$")
    guardian_email: str | None = Field(default=None, max_length=320)
    relationship_type: str = Field(..., pattern="^(FATHER|MOTHER|LEGAL_GUARDIAN|RELATIVE|SPONSOR|OTHER)$")


class LookupItem(BaseModel):
    id: UUID
    name: str

class AcademicYearLookup(LookupItem):
    pass

class ProgrammeLookup(LookupItem):
    pass

class BatchLookup(LookupItem):
    pass

class SectionLookup(LookupItem):
    pass


class ManualAddStudentResponse(BaseModel):
    student_id: UUID
    guardian_id: UUID | None = None
    enrollment_id: UUID
    student_number: str
    message: str = "Student created successfully"


class ActivatePortalResponse(BaseModel):
    guardian_id: UUID
    portal_user_id: UUID | None = None
    status: str
    message: str


class BulkActivateSectionRequest(BaseModel):
    branch_id: UUID
    academic_year_id: UUID
    programme_id: UUID | None = None
    batch_id: UUID | None = None
    section_id: UUID


class BulkActivationResult(BaseModel):
    guardian_id: UUID
    guardian_name: str
    student_names: list[str]
    status: str
    reason: str | None = None


class BulkActivateSectionResponse(BaseModel):
    total_students: int
    unique_guardians: int
    eligible_count: int
    activated_count: int
    already_active_count: int
    missing_contact_count: int
    failed_count: int
    results: list[BulkActivationResult]


class BulkActivateEligibilityResponse(BaseModel):
    total_students: int
    unique_guardians: int
    eligible_count: int
    already_active_count: int
    missing_contact_count: int
