"""Examinations module Pydantic schemas."""

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExamSubjectCreate(BaseModel):
    subject_id: UUID
    subject_name: str
    subject_code: str
    maximum_marks: int = 100
    pass_marks: int = 35


class ExamSubjectRead(BaseModel):
    id: UUID
    tenant_id: UUID
    exam_id: UUID
    subject_id: UUID
    subject_name: str
    subject_code: str
    maximum_marks: int
    pass_marks: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamCreate(BaseModel):
    scope: str
    branch_id: Optional[UUID] = None
    branch_ids: Optional[List[str]] = None
    academic_year_id: UUID
    programme_id: UUID
    name: str
    type: str
    exam_date: date
    marks_entry_deadline: Optional[date] = None
    subjects: Optional[List[ExamSubjectCreate]] = None


class ExamRead(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: Optional[UUID] = None
    scope: str
    branch_ids: Optional[List[str]] = None
    excluded_branch_ids: Optional[List[str]] = None
    exemption_reasons: Optional[Dict[str, str]] = None
    academic_year_id: UUID
    programme_id: UUID
    name: str
    type: str
    exam_date: date
    marks_entry_deadline: Optional[date] = None
    status: str
    return_reason: Optional[str] = None
    published_at: Optional[datetime] = None
    published_by: Optional[UUID] = None
    created_by: UUID
    updated_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamDateOverlapCheckRequest(BaseModel):
    exam_date: date
    target_branch_ids: List[str]
    programme_id: str
    section_ids: Optional[List[str]] = None
    exclude_exam_id: Optional[str] = None


class ExamDateOverlapCheckResponse(BaseModel):
    has_overlap: bool
    overlapping_exam_id: Optional[UUID] = None
    overlapping_exam_name: Optional[str] = None
    message: Optional[str] = None


class BranchExemptionRequest(BaseModel):
    branch_id: UUID
    reason: str


class ReturnForCorrectionRequest(BaseModel):
    reason: str


class StudentExamRecordItem(BaseModel):
    enrollment_id: UUID
    student_id: UUID
    section_id: UUID
    subject_marks: Dict[str, float]
    status: str = "DRAFT"


class StudentExamRecordBulkSaveRequest(BaseModel):
    records: List[StudentExamRecordItem]


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

    model_config = ConfigDict(from_attributes=True)
