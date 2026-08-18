"""Dashboard application service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status

from app.core.security.context import RequestContext
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import (
    DashboardAttendanceSummary,
    DashboardExamSummary,
    DashboardFeeSummary,
    DashboardImportSummary,
    DashboardQuickAction,
    DashboardScope,
    DashboardStudentSummary,
    DashboardSummaryCard,
    OfficeStaffDashboardResponse,
)


class DashboardService:
    """Build read-only dashboard responses."""

    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    def get_office_staff_dashboard(self, context: RequestContext) -> OfficeStaffDashboardResponse:
        """Return the operational dashboard for branch-scoped staff users."""

        if context.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant scope required.",
            )
        if context.branch_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Branch scope required.",
            )
        if "dashboard" not in context.enabled_modules:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Module disabled.",
            )

        today = date.today()
        student_counts = self.repository.get_student_summary(context.tenant_id, context.branch_id)
        fee_counts = self.repository.get_fee_summary(context.tenant_id, context.branch_id)
        attendance_counts = self.repository.get_attendance_summary(
            context.tenant_id,
            context.branch_id,
            today,
        )
        import_counts = self.repository.get_import_summary(context.tenant_id, context.branch_id)
        exam_counts = self.repository.get_exam_summary(context.tenant_id, context.branch_id)

        students = DashboardStudentSummary(
            **student_counts,
            recent_students=self.repository.get_recent_students(
                context.tenant_id,
                context.branch_id,
            ),
        )
        fees = DashboardFeeSummary(
            **fee_counts,
            recent_payments=self.repository.get_recent_payments(
                context.tenant_id,
                context.branch_id,
            ),
        )
        attendance = DashboardAttendanceSummary(
            today=today,
            **attendance_counts,
            recent_sessions=self.repository.get_recent_attendance_sessions(
                context.tenant_id,
                context.branch_id,
            ),
        )
        imports = DashboardImportSummary(**import_counts)
        examinations = DashboardExamSummary(
            **exam_counts,
            latest_exams=self.repository.get_latest_exams(context.tenant_id, context.branch_id),
        )

        return OfficeStaffDashboardResponse(
            scope=DashboardScope(
                tenant_id=context.tenant_id,
                branch_id=context.branch_id,
                branch_name=self.repository.get_branch_name(context.tenant_id, context.branch_id),
                role_codes=sorted(context.canonical_role_codes),
            ),
            generated_at=datetime.now(UTC),
            summary_cards=self._summary_cards(students, attendance, fees, imports, examinations),
            quick_actions=self._quick_actions(context),
            students=students,
            attendance=attendance,
            fees=fees,
            imports=imports,
            examinations=examinations,
        )

    def _summary_cards(
        self,
        students: DashboardStudentSummary,
        attendance: DashboardAttendanceSummary,
        fees: DashboardFeeSummary,
        imports: DashboardImportSummary,
        examinations: DashboardExamSummary,
    ) -> list[DashboardSummaryCard]:
        return [
            DashboardSummaryCard(
                key="active_students",
                label="Active Students",
                value=students.active_students,
                helper=f"{students.students_created_this_week} added this week",
                route="/students",
            ),
            DashboardSummaryCard(
                key="attendance_today",
                label="Attendance Today",
                value=attendance.sessions_today,
                helper=f"{attendance.sections_without_session} sections still not started",
                tone="warning" if attendance.sections_without_session else "success",
                route="/attendance",
            ),
            DashboardSummaryCard(
                key="fee_outstanding",
                label="Fee Outstanding",
                value=fees.outstanding,
                helper=f"{fees.accounts_with_due} accounts with dues",
                tone="danger" if fees.outstanding > Decimal("0") else "success",
                route="/fees",
            ),
            DashboardSummaryCard(
                key="payments_today",
                label="Payments Today",
                value=fees.payments_today,
                helper="Posted receipts today",
                tone="success",
                route="/fees",
            ),
            DashboardSummaryCard(
                key="pending_imports",
                label="Pending Imports",
                value=imports.pending_batches,
                helper=f"{imports.total_recent_batches} recent batches",
                tone="warning" if imports.pending_batches else "neutral",
                route="/imports",
            ),
            DashboardSummaryCard(
                key="exam_work",
                label="Exam Work",
                value=examinations.marks_entry_pending,
                helper=f"{examinations.upcoming_exams} upcoming exams",
                route="/examinations",
            ),
        ]

    def _quick_actions(self, context: RequestContext) -> list[DashboardQuickAction]:
        actions = [
            DashboardQuickAction(
                label="Add Student",
                description="Create one student and guardian record.",
                route="/imports/manual",
                module="imports",
                permission="import.upload",
            ),
            DashboardQuickAction(
                label="Import Students",
                description="Upload and validate the student template.",
                route="/imports/template",
                module="imports",
                permission="import.upload",
            ),
            DashboardQuickAction(
                label="Import Fee Data",
                description="Bulk create or update fee accounts.",
                route="/imports/fees",
                module="imports",
                permission="import.upload",
            ),
            DashboardQuickAction(
                label="Record Fee Payment",
                description="Post payment receipts against fee ledgers.",
                route="/fees",
                module="fees",
                permission="fee.payment_record",
            ),
            DashboardQuickAction(
                label="Mark Attendance",
                description="Open attendance for a section.",
                route="/attendance",
                module="attendance",
                permission="attendance.mark",
            ),
            DashboardQuickAction(
                label="Enter Marks",
                description="Open examination marks entry.",
                route="/examinations",
                module="examinations",
                permission="exam.marks_enter",
            ),
        ]
        return [
            action
            for action in actions
            if action.module in context.enabled_modules
            and (action.permission is None or action.permission in context.permission_keys)
        ]
