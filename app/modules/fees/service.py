"""Fee module service layer."""

from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status

from app.modules.fees.repository import FeeRepository
from app.modules.fees.schemas import (
    FeeAccountCreateRequest,
    FeeAccountListItem,
    FeeEnrollmentOption,
    FeeLedgerEntryItem,
    FeeLedgerResponse,
    FeePaymentCreateRequest,
    FeePaymentPostResponse,
)


class FeeService:
    """Coordinates fee use cases without bypassing tenant/branch scope."""

    def __init__(self, repository: FeeRepository) -> None:
        self.repository = repository

    def list_fee_accounts(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
    ) -> list[FeeAccountListItem]:
        rows = self.repository.list_fee_accounts(tenant_id=tenant_id, branch_id=branch_id)
        return [
            FeeAccountListItem(
                **row,
                student_name=row["display_name"] or row["legal_name"],
            )
            for row in rows
        ]

    def list_fee_setup_options(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
    ) -> list[FeeEnrollmentOption]:
        rows = self.repository.list_enrollments_without_fee_accounts(
            tenant_id=tenant_id,
            branch_id=branch_id,
        )
        return [
            FeeEnrollmentOption(
                **row,
                student_name=row["display_name"] or row["legal_name"],
            )
            for row in rows
        ]

    def create_fee_account(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        app_user_id: UUID,
        payload: FeeAccountCreateRequest,
    ) -> FeeAccountListItem:
        enrollment = self.repository.get_active_enrollment_for_fee_setup(
            tenant_id=tenant_id,
            branch_id=branch_id,
            enrollment_id=payload.enrollment_id,
        )
        if enrollment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active enrollment was not found for this fee setup context.",
            )
        if enrollment["fee_account_id"] is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A fee account already exists for this enrollment.",
            )

        net_payable = (
            payload.assigned_fee_amount
            - payload.scholarship_amount
            - payload.concession_amount
        )
        account_id = self.repository.create_fee_account(
            {
                "id": uuid.uuid4(),
                "tenant_id": tenant_id,
                "branch_id": enrollment["branch_id"],
                "student_id": enrollment["student_id"],
                "enrollment_id": enrollment["enrollment_id"],
                "academic_year_id": enrollment["academic_year_id"],
                "assigned_fee_amount": payload.assigned_fee_amount,
                "scholarship_amount": payload.scholarship_amount,
                "concession_amount": payload.concession_amount,
                "net_payable_amount": net_payable,
                "total_paid_amount": Decimal("0"),
                "total_adjusted_amount": Decimal("0"),
                "total_reversed_amount": Decimal("0"),
                "outstanding_amount": net_payable,
                "payment_schedule_type": payload.payment_schedule_type,
                "payment_schedule": [],
                "status": "PAID" if net_payable == 0 else "ACTIVE",
                "created_by": app_user_id,
            }
        )

        self._create_initial_ledger_entries(
            tenant_id=tenant_id,
            account_id=account_id,
            enrollment=enrollment,
            app_user_id=app_user_id,
            assigned_fee_amount=payload.assigned_fee_amount,
            scholarship_amount=payload.scholarship_amount,
            concession_amount=payload.concession_amount,
        )
        self.repository.session.commit()

        row = self.repository.get_fee_account_list_item(tenant_id=tenant_id, account_id=account_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Fee account was created but could not be loaded.",
            )
        return FeeAccountListItem(**row, student_name=row["display_name"] or row["legal_name"])

    def get_fee_ledger(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        account_id: UUID,
    ) -> FeeLedgerResponse:
        account = self.repository.get_fee_account_for_context(
            tenant_id=tenant_id,
            branch_id=branch_id,
            account_id=account_id,
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee account not found.",
            )

        row = self.repository.get_fee_account_list_item(
            tenant_id=tenant_id,
            account_id=account_id,
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee account not found.",
            )

        entries = self.repository.list_fee_ledger_entries(
            tenant_id=tenant_id,
            branch_id=branch_id,
            account_id=account_id,
        )
        return FeeLedgerResponse(
            fee_account=FeeAccountListItem(
                **row,
                student_name=row["display_name"] or row["legal_name"],
            ),
            entries=[FeeLedgerEntryItem(**entry) for entry in entries],
        )

    def _create_initial_ledger_entries(
        self,
        *,
        tenant_id: UUID,
        account_id: UUID,
        enrollment: dict[str, object],
        app_user_id: UUID,
        assigned_fee_amount: Decimal,
        scholarship_amount: Decimal,
        concession_amount: Decimal,
    ) -> None:
        common = {
            "tenant_id": tenant_id,
            "branch_id": enrollment["branch_id"],
            "fee_account_id": account_id,
            "student_id": enrollment["student_id"],
            "enrollment_id": enrollment["enrollment_id"],
            "academic_year_id": enrollment["academic_year_id"],
            "posted_by": app_user_id,
            "created_by": app_user_id,
            "status": "POSTED",
        }
        if assigned_fee_amount > 0:
            self.repository.create_ledger_entry(
                {
                    **common,
                    "entry_type": "FEE_ASSIGNED",
                    "balance_effect": "INCREASE",
                    "amount": assigned_fee_amount,
                    "notes": "Initial fee account setup.",
                }
            )
        if scholarship_amount > 0:
            self.repository.create_ledger_entry(
                {
                    **common,
                    "entry_type": "GOVERNMENT_SCHOLARSHIP",
                    "balance_effect": "DECREASE",
                    "amount": scholarship_amount,
                    "notes": "Scholarship recorded during initial fee setup.",
                }
            )
        if concession_amount > 0:
            self.repository.create_ledger_entry(
                {
                    **common,
                    "entry_type": "CONCESSION",
                    "balance_effect": "DECREASE",
                    "amount": concession_amount,
                    "notes": "Concession recorded during initial fee setup.",
                }
            )

    def post_payment(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        app_user_id: UUID,
        account_id: UUID,
        payload: FeePaymentCreateRequest,
    ) -> FeePaymentPostResponse:
        account = self.repository.get_fee_account_for_payment(
            tenant_id=tenant_id,
            branch_id=branch_id,
            account_id=account_id,
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Fee account not found.",
            )
        if account["status"] in {"CANCELLED", "CLOSED"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payments cannot be posted to a closed or cancelled fee account.",
            )

        outstanding_amount = Decimal(account["outstanding_amount"])
        total_paid_amount = Decimal(account["total_paid_amount"])
        if payload.amount > outstanding_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount cannot exceed the current outstanding amount.",
            )

        new_total_paid = total_paid_amount + payload.amount
        new_outstanding = outstanding_amount - payload.amount
        new_status = "PAID" if new_outstanding == 0 else "PARTIALLY_PAID"
        receipt_number = self.repository.next_receipt_number(
            tenant_id=tenant_id,
            branch_id=account["branch_id"],
        )

        try:
            ledger_entry_id = self.repository.create_ledger_entry(
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "branch_id": account["branch_id"],
                    "fee_account_id": account["id"],
                    "student_id": account["student_id"],
                    "enrollment_id": account["enrollment_id"],
                    "academic_year_id": account["academic_year_id"],
                    "entry_type": "PAYMENT",
                    "balance_effect": "DECREASE",
                    "amount": payload.amount,
                    "payment_mode": payload.payment_mode,
                    "external_reference": payload.external_reference,
                    "receipt_number": receipt_number,
                    "receipt_date": payload.receipt_date,
                    "payment_period_label": payload.payment_period_label,
                    "installment_number": payload.installment_number,
                    "notes": payload.notes,
                    "collected_by": app_user_id,
                    "posted_by": app_user_id,
                    "created_by": app_user_id,
                    "status": "POSTED",
                }
            )
            self.repository.update_fee_account_totals(
                account_id=account["id"],
                total_paid_amount=new_total_paid,
                outstanding_amount=new_outstanding,
                status=new_status,
                updated_by=app_user_id,
            )
            self.repository.session.commit()
        except Exception as exc:
            self.repository.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to post payment.",
            ) from exc

        row = self.repository.get_fee_account_list_item(
            tenant_id=tenant_id,
            account_id=account["id"],
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment posted but fee account could not be loaded.",
            )
        return FeePaymentPostResponse(
            fee_account=FeeAccountListItem(
                **row,
                student_name=row["display_name"] or row["legal_name"],
            ),
            ledger_entry_id=ledger_entry_id,
            receipt_number=receipt_number,
        )
