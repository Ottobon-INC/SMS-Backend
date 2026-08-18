"""Pydantic schemas for operational dashboards."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class DashboardScope(BaseModel):
    """Scope used to build the office-staff dashboard."""

    tenant_id: UUID
    branch_id: UUID | None
    branch_name: str | None
    role_codes: list[str]


class DashboardSummaryCard(BaseModel):
    """One high-level metric card."""

    key: str
    label: str
    value: int | Decimal | str
    helper: str | None = None
    tone: str = "neutral"
    route: str | None = None


class DashboardQuickAction(BaseModel):
    """Permission-driven action shown on the dashboard."""

    label: str
    description: str
    route: str
    module: str
    permission: str | None = None


class DashboardAttendanceSummary(BaseModel):
    """Branch attendance snapshot for the current day."""

    today: date
    sessions_today: int
    draft_sessions: int
    submitted_sessions: int
    finalized_sessions: int
    total_sections: int
    sections_without_session: int
    recent_sessions: list[dict[str, object]] = Field(default_factory=list)


class DashboardFeeSummary(BaseModel):
    """Fee ledger totals visible to Office Staff."""

    active_accounts: int
    net_payable: Decimal
    paid: Decimal
    outstanding: Decimal
    payments_today: Decimal
    accounts_with_due: int
    recent_payments: list[dict[str, object]] = Field(default_factory=list)


class DashboardStudentSummary(BaseModel):
    """Student operational counters."""

    active_students: int
    current_enrollments: int
    students_created_today: int
    students_created_this_week: int
    missing_guardian_contact: int
    missing_fee_accounts: int
    recent_students: list[dict[str, object]] = Field(default_factory=list)


class DashboardImportSummary(BaseModel):
    """Recent import activity."""

    total_recent_batches: int
    pending_batches: int
    failed_or_rejected_batches: int
    latest_batches: list[dict[str, object]] = Field(default_factory=list)


class DashboardExamSummary(BaseModel):
    """Exam operations visible to Office Staff."""

    upcoming_exams: int
    draft_exams: int
    returned_exams: int
    marks_entry_pending: int
    latest_exams: list[dict[str, object]] = Field(default_factory=list)


class OfficeStaffDashboardResponse(BaseModel):
    """Complete response consumed by the Office Staff dashboard."""

    scope: DashboardScope
    generated_at: datetime
    summary_cards: list[DashboardSummaryCard]
    quick_actions: list[DashboardQuickAction]
    students: DashboardStudentSummary
    attendance: DashboardAttendanceSummary
    fees: DashboardFeeSummary
    imports: DashboardImportSummary
    examinations: DashboardExamSummary
