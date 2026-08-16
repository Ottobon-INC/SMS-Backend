"""Database access for the fee module."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.orm import Session

from app.modules.academic_structure.models import AcademicProgramme, AcademicYear, Section
from app.modules.branches.models import Branch
from app.modules.fees.models import FeeAccount, FeeLedgerEntry
from app.modules.students.models import Enrollment, Student
from app.modules.users.models import AppUser


class FeeRepository:
    """Tenant- and branch-scoped fee queries."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_fee_accounts(self, *, tenant_id: UUID, branch_id: UUID | None) -> list[dict[str, Any]]:
        fee_account = FeeAccount.__table__
        student = Student.__table__
        enrollment = Enrollment.__table__
        branch = Branch.__table__
        academic_year = AcademicYear.__table__
        programme = AcademicProgramme.__table__
        section = Section.__table__

        statement = (
            select(
                fee_account.c.id,
                fee_account.c.tenant_id,
                fee_account.c.branch_id,
                fee_account.c.student_id,
                fee_account.c.enrollment_id,
                fee_account.c.academic_year_id,
                enrollment.c.admission_number,
                student.c.display_name,
                student.c.legal_name,
                branch.c.display_name.label("branch_name"),
                academic_year.c.name.label("academic_year"),
                programme.c.programme_name,
                section.c.section_name,
                fee_account.c.currency,
                fee_account.c.assigned_fee_amount,
                fee_account.c.scholarship_amount,
                fee_account.c.concession_amount,
                fee_account.c.net_payable_amount,
                fee_account.c.total_paid_amount,
                fee_account.c.total_adjusted_amount,
                fee_account.c.total_reversed_amount,
                fee_account.c.outstanding_amount,
                fee_account.c.payment_schedule_type,
                fee_account.c.status,
            )
            .select_from(
                fee_account.join(
                    student,
                    and_(
                        fee_account.c.tenant_id == student.c.tenant_id,
                        fee_account.c.student_id == student.c.id,
                    ),
                )
                .join(
                    enrollment,
                    and_(
                        fee_account.c.tenant_id == enrollment.c.tenant_id,
                        fee_account.c.enrollment_id == enrollment.c.id,
                    ),
                )
                .join(
                    branch,
                    and_(
                        fee_account.c.tenant_id == branch.c.tenant_id,
                        fee_account.c.branch_id == branch.c.id,
                    ),
                )
                .join(
                    academic_year,
                    and_(
                        fee_account.c.tenant_id == academic_year.c.tenant_id,
                        fee_account.c.academic_year_id == academic_year.c.id,
                    ),
                )
                .outerjoin(
                    programme,
                    and_(
                        enrollment.c.tenant_id == programme.c.tenant_id,
                        enrollment.c.programme_id == programme.c.id,
                    ),
                )
                .outerjoin(
                    section,
                    and_(
                        enrollment.c.tenant_id == section.c.tenant_id,
                        enrollment.c.branch_id == section.c.branch_id,
                        enrollment.c.batch_id == section.c.batch_id,
                        enrollment.c.section_id == section.c.id,
                    ),
                )
            )
            .where(fee_account.c.tenant_id == tenant_id)
            .order_by(fee_account.c.created_at.desc())
        )
        if branch_id is not None:
            statement = statement.where(fee_account.c.branch_id == branch_id)

        rows = self.session.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def list_enrollments_without_fee_accounts(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
    ) -> list[dict[str, Any]]:
        fee_account = FeeAccount.__table__
        student = Student.__table__
        enrollment = Enrollment.__table__
        branch = Branch.__table__
        academic_year = AcademicYear.__table__
        programme = AcademicProgramme.__table__
        section = Section.__table__

        statement = (
            select(
                enrollment.c.id.label("enrollment_id"),
                enrollment.c.student_id,
                enrollment.c.branch_id,
                enrollment.c.academic_year_id,
                enrollment.c.admission_number,
                student.c.display_name,
                student.c.legal_name,
                branch.c.display_name.label("branch_name"),
                academic_year.c.name.label("academic_year"),
                programme.c.programme_name,
                section.c.section_name,
            )
            .select_from(
                enrollment.join(
                    student,
                    and_(
                        enrollment.c.tenant_id == student.c.tenant_id,
                        enrollment.c.student_id == student.c.id,
                    ),
                )
                .join(
                    branch,
                    and_(
                        enrollment.c.tenant_id == branch.c.tenant_id,
                        enrollment.c.branch_id == branch.c.id,
                    ),
                )
                .join(
                    academic_year,
                    and_(
                        enrollment.c.tenant_id == academic_year.c.tenant_id,
                        enrollment.c.academic_year_id == academic_year.c.id,
                    ),
                )
                .outerjoin(
                    programme,
                    and_(
                        enrollment.c.tenant_id == programme.c.tenant_id,
                        enrollment.c.programme_id == programme.c.id,
                    ),
                )
                .outerjoin(
                    section,
                    and_(
                        enrollment.c.tenant_id == section.c.tenant_id,
                        enrollment.c.branch_id == section.c.branch_id,
                        enrollment.c.batch_id == section.c.batch_id,
                        enrollment.c.section_id == section.c.id,
                    ),
                )
                .outerjoin(
                    fee_account,
                    and_(
                        enrollment.c.tenant_id == fee_account.c.tenant_id,
                        enrollment.c.id == fee_account.c.enrollment_id,
                    ),
                )
            )
            .where(
                enrollment.c.tenant_id == tenant_id,
                enrollment.c.is_current.is_(True),
                enrollment.c.status == "ACTIVE",
                fee_account.c.id.is_(None),
            )
            .order_by(student.c.legal_name.asc(), enrollment.c.admission_number.asc())
        )
        if branch_id is not None:
            statement = statement.where(enrollment.c.branch_id == branch_id)

        rows = self.session.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def get_active_enrollment_for_fee_setup(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        enrollment_id: UUID,
    ) -> dict[str, Any] | None:
        enrollment = Enrollment.__table__
        student = Student.__table__
        fee_account = FeeAccount.__table__

        statement = (
            select(
                enrollment.c.id.label("enrollment_id"),
                enrollment.c.tenant_id,
                enrollment.c.student_id,
                enrollment.c.branch_id,
                enrollment.c.academic_year_id,
                fee_account.c.id.label("fee_account_id"),
            )
            .select_from(
                enrollment.join(
                    student,
                    and_(
                        enrollment.c.tenant_id == student.c.tenant_id,
                        enrollment.c.student_id == student.c.id,
                    ),
                ).outerjoin(
                    fee_account,
                    and_(
                        enrollment.c.tenant_id == fee_account.c.tenant_id,
                        enrollment.c.id == fee_account.c.enrollment_id,
                    ),
                )
            )
            .where(
                enrollment.c.id == enrollment_id,
                enrollment.c.tenant_id == tenant_id,
                enrollment.c.is_current.is_(True),
                enrollment.c.status == "ACTIVE",
                student.c.current_status == "ACTIVE",
            )
        )
        if branch_id is not None:
            statement = statement.where(enrollment.c.branch_id == branch_id)

        row = self.session.execute(statement).mappings().first()
        return dict(row) if row else None

    def create_fee_account(self, values: dict[str, Any]) -> UUID:
        table = FeeAccount.__table__
        row = self.session.execute(insert(table).values(**values).returning(table.c.id)).one()
        return UUID(str(row[0]))

    def create_ledger_entry(self, values: dict[str, Any]) -> UUID:
        table = FeeLedgerEntry.__table__
        row = self.session.execute(insert(table).values(**values).returning(table.c.id)).one()
        return UUID(str(row[0]))

    def get_fee_account_for_payment(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        account_id: UUID,
    ) -> dict[str, Any] | None:
        table = FeeAccount.__table__
        statement = (
            select(table)
            .where(
                table.c.id == account_id,
                table.c.tenant_id == tenant_id,
            )
            .with_for_update()
        )
        if branch_id is not None:
            statement = statement.where(table.c.branch_id == branch_id)
        row = self.session.execute(statement).mappings().first()
        return dict(row) if row else None

    def get_fee_account_for_context(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        account_id: UUID,
    ) -> dict[str, Any] | None:
        table = FeeAccount.__table__
        statement = select(table).where(
            table.c.id == account_id,
            table.c.tenant_id == tenant_id,
        )
        if branch_id is not None:
            statement = statement.where(table.c.branch_id == branch_id)
        row = self.session.execute(statement).mappings().first()
        return dict(row) if row else None

    def list_fee_ledger_entries(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        account_id: UUID,
    ) -> list[dict[str, Any]]:
        ledger = FeeLedgerEntry.__table__
        collected_user = AppUser.__table__.alias("collected_user")
        posted_user = AppUser.__table__.alias("posted_user")

        statement = (
            select(
                ledger.c.id,
                ledger.c.entry_type,
                ledger.c.balance_effect,
                ledger.c.amount,
                ledger.c.payment_mode,
                ledger.c.external_reference,
                ledger.c.receipt_number,
                ledger.c.receipt_date,
                ledger.c.payment_period_label,
                ledger.c.installment_number,
                ledger.c.entry_date,
                ledger.c.status,
                ledger.c.notes,
                collected_user.c.full_name.label("collected_by_name"),
                posted_user.c.full_name.label("posted_by_name"),
                ledger.c.posted_at,
                ledger.c.created_at,
            )
            .select_from(
                ledger.outerjoin(
                    collected_user,
                    ledger.c.collected_by == collected_user.c.id,
                ).outerjoin(
                    posted_user,
                    ledger.c.posted_by == posted_user.c.id,
                )
            )
            .where(
                ledger.c.tenant_id == tenant_id,
                ledger.c.fee_account_id == account_id,
            )
            .order_by(
                ledger.c.entry_date.asc(),
                ledger.c.created_at.asc(),
                ledger.c.entry_type.asc(),
            )
        )
        if branch_id is not None:
            statement = statement.where(ledger.c.branch_id == branch_id)

        rows = self.session.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def update_fee_account_totals(
        self,
        *,
        account_id: UUID,
        total_paid_amount: Any,
        outstanding_amount: Any,
        status: str,
        updated_by: UUID,
    ) -> None:
        table = FeeAccount.__table__
        self.session.execute(
            update(table)
            .where(table.c.id == account_id)
            .values(
                total_paid_amount=total_paid_amount,
                outstanding_amount=outstanding_amount,
                status=status,
                updated_by=updated_by,
            )
        )
        self.session.flush()

    def next_receipt_number(self, *, tenant_id: UUID, branch_id: UUID) -> str:
        table = FeeLedgerEntry.__table__
        count = self.session.execute(
            select(func.count())
            .where(
                table.c.tenant_id == tenant_id,
                table.c.branch_id == branch_id,
                table.c.entry_type == "PAYMENT",
                table.c.receipt_number.is_not(None),
            )
        ).scalar_one()
        return f"RCP-{count + 1:06d}"

    def get_fee_account_list_item(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
    ) -> dict[str, Any] | None:
        rows = self.list_fee_accounts(tenant_id=tenant_id, branch_id=None)
        for row in rows:
            if row["id"] == account_id:
                return row
        return None
