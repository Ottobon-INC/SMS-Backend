# ruff: noqa: B008, E501
"""Examinations module Pydantic schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

# --- ExamSubject Schemas ---

class ExamSubjectBase(BaseModel):
    subject_id: UUID | str
    subject_name: str
    subject_code: str
    maximum_marks: int = Field(gt=0, default=100)
    pass_marks: int = Field(ge=0, default=35)


class ExamSubjectCreate(ExamSubjectBase):
    pass


class ExamSubjectRead(ExamSubjectBase):
    id: UUID
    tenant_id: UUID
    exam_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# --- Exam Schemas ---

class ExamBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    type: str = Field(min_length=1, max_length=50)
    scope: str = Field(default="SINGLE_BRANCH")  # SINGLE_BRANCH, ALL_BRANCHES, SELECTED_BRANCHES
    branch_id: UUID | str | None = None
    branch_ids: list[str] | None = None
    excluded_branch_ids: list[str] | None = None
    exemption_reasons: dict[str, str] | None = None
    academic_year_id: UUID | str
    programme_id: UUID | str
    programme_ids: list[str] | None = None
    exam_date: date
    marks_entry_deadline: date | None = None


class ExamCreate(ExamBase):
    exam_subjects: list[ExamSubjectCreate] | None = None


class ExamUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    scope: str | None = None
    branch_id: UUID | None = None
    branch_ids: list[str] | None = None
    excluded_branch_ids: list[str] | None = None
    exemption_reasons: dict[str, str] | None = None
    programme_ids: list[str] | None = None
    exam_date: date | None = None
    marks_entry_deadline: date | None = None
    status: str | None = None
    return_reason: str | None = None


class ExamRead(ExamBase):
    id: UUID
    tenant_id: UUID
    status: str
    marks_summary: dict[str, int] | None = None
    return_reason: str | None = None
    published_at: datetime | None = None
    published_by: UUID | None = None
    created_by: UUID
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    exam_subjects: list[ExamSubjectRead] = []

    class Config:
        from_attributes = True


# --- Workflow Requests ---

class ExamDateOverlapCheckRequest(BaseModel):
    exam_date: date
    target_branch_ids: list[str]
    programme_id: str
    section_ids: list[str] | None = None
    exclude_exam_id: str | None = None


class ExamDateOverlapCheckResponse(BaseModel):
    has_overlap: bool
    conflicting_exam_id: str | None = None
    conflicting_exam_name: str | None = None


class BranchExemptionRequest(BaseModel):
    branch_id: str
    reason: str


class ReturnForCorrectionRequest(BaseModel):
    reason: str


# --- StudentExamRecord Schemas ---

class StudentExamRecordSave(BaseModel):
    enrollment_id: str | UUID
    student_id: str | UUID
    section_id: str | UUID
    subject_marks: dict[str, float] = {}
    status: str | None = "DRAFT"


class StudentExamRecordBulkSaveRequest(BaseModel):
    records: list[StudentExamRecordSave]


class StudentExamRecordRead(BaseModel):
    id: UUID
    tenant_id: UUID
    exam_id: UUID
    enrollment_id: str | UUID
    student_id: str | UUID
    section_id: str | UUID
    subject_marks: dict[str, float] = {}
    status: str
    entered_by: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
