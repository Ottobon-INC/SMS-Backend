"""Attendance module Pydantic schemas."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# Using string literals for UUIDs in response, accepting str in requests
class AttendanceSessionCreate(BaseModel):
    sectionId: str
    attendanceDate: date

class AttendanceRecordUpdate(BaseModel):
    enrollmentId: str
    attendanceStatus: Literal["PRESENT", "ABSENT", "LEAVE", "UNMARKED"]
    note: str | None = None

class AttendanceDraftSavePayload(BaseModel):
    records: list[AttendanceRecordUpdate]

class AttendanceStudentResponse(BaseModel):
    enrollmentId: str
    studentId: str
    studentName: str
    admissionNumber: str | None = None
    rollNumber: str | None = None
    attendanceStatus: Literal["PRESENT", "ABSENT", "LEAVE", "UNMARKED"]
    note: str | None = None

class AttendanceSessionResponse(BaseModel):
    id: str
    tenantId: str
    branchId: str
    academicYearId: str
    sectionId: str
    attendanceDate: date
    status: Literal["DRAFT", "SUBMITTED", "FINALIZED"]
    openedBy: str
    submittedBy: str | None = None
    submittedAt: datetime | None = None
    finalizedBy: str | None = None
    finalizedAt: datetime | None = None
    students: list[AttendanceStudentResponse] = Field(default_factory=list)

class AttendanceSessionListItem(BaseModel):
    id: str
    tenantId: str
    branchId: str
    academicYearId: str
    sectionId: str
    sectionName: str
    batchName: str
    programmeName: str | None = None
    attendanceDate: date
    status: Literal["DRAFT", "SUBMITTED", "FINALIZED"]
    openedBy: str
    submittedBy: str | None = None
    submittedAt: datetime | None = None
    finalizedBy: str | None = None
    finalizedAt: datetime | None = None

class ReturnAttendancePayload(BaseModel):
    reason: str | None = None
