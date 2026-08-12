"""Examinations module Pydantic schemas."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# --- ExamSubject Schemas ---

class ExamSubjectBase(BaseModel):
    subject_id: UUID
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
    branch_id: Optional[UUID] = None
    branch_ids: Optional[List[str]] = None
    excluded_branch_ids: Optional[List[str]] = None
    exemption_reasons: Optional[Dict[str, str]] = None
    academic_year_id: UUID
    programme_id: UUID
    programme_ids: Optional[List[str]] = None
    exam_date: date
    marks_entry_deadline: Optional[date] = None


class ExamCreate(ExamBase):
    exam_subjects: Optional[List[ExamSubjectCreate]] = None


class ExamUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    scope: Optional[str] = None
    branch_id: Optional[UUID] = None
    branch_ids: Optional[List[str]] = None
    excluded_branch_ids: Optional[List[str]] = None
    exemption_reasons: Optional[Dict[str, str]] = None
    programme_ids: Optional[List[str]] = None
    exam_date: Optional[date] = None
    marks_entry_deadline: Optional[date] = None
    status: Optional[str] = None
    return_reason: Optional[str] = None


class ExamRead(ExamBase):
    id: UUID
    tenant_id: UUID
    status: str
    return_reason: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[UUID] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    exam_subjects: List[ExamSubjectRead] = []

    class Config:
        from_attributes = True


# --- Workflow Requests ---

class ExamDateOverlapCheckRequest(BaseModel):
    exam_date: date
    target_branch_ids: List[str]
    programme_id: str
    section_ids: Optional[List[str]] = None
    exclude_exam_id: Optional[str] = None


class ExamDateOverlapCheckResponse(BaseModel):
    has_overlap: bool
    conflicting_exam_id: Optional[str] = None
    conflicting_exam_name: Optional[str] = None


class BranchExemptionRequest(BaseModel):
    branch_id: str
    reason: str


class ReturnForCorrectionRequest(BaseModel):
    reason: str


# --- StudentExamRecord Schemas ---

class StudentExamRecordSave(BaseModel):
    enrollment_id: UUID
    student_id: UUID
    section_id: UUID
    subject_marks: Dict[str, float]  # subject_id -> mark score (-1: ABSENT, -2: EXEMPTED, -3: MALPRACTICE)
    status: Optional[str] = "DRAFT"


class StudentExamRecordBulkSaveRequest(BaseModel):
    records: List[StudentExamRecordSave]


class StudentExamRecordRead(BaseModel):
    id: UUID
    tenant_id: UUID
    exam_id: UUID
    enrollment_id: UUID
    student_id: UUID
    section_id: UUID
    subject_marks: Dict[str, float]
    status: str
    entered_by: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
