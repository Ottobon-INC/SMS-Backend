"""Pydantic schemas for read-only fee account responses."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

PaymentScheduleType = Literal["ONE_TIME", "TERM_WISE", "INSTALLMENT_WISE", "CUSTOM"]
PaymentMode = Literal["CASH", "UPI", "BANK_TRANSFER", "CHEQUE", "CARD", "OTHER"]


class FeeAccountListItem(BaseModel):
    """Student fee account row returned to operational users."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    branch_id: UUID
    student_id: UUID
    enrollment_id: UUID
    academic_year_id: UUID
    admission_number: str | None
    student_name: str
    branch_name: str | None
    academic_year: str | None
    year_level: str | None = None
    year_level_label: str | None = None
    programme_code: str | None = None
    programme_name: str | None
    programme_display: str | None = None
    section_name: str | None
    section_display: str | None = None
    currency: str
    assigned_fee_amount: Decimal
    scholarship_amount: Decimal
    concession_amount: Decimal
    net_payable_amount: Decimal
    total_paid_amount: Decimal
    total_adjusted_amount: Decimal
    total_reversed_amount: Decimal
    outstanding_amount: Decimal
    payment_schedule_type: str
    status: str


class FeeEnrollmentOption(BaseModel):
    """Active enrollment that can receive a fee account."""

    enrollment_id: UUID
    student_id: UUID
    branch_id: UUID
    academic_year_id: UUID
    admission_number: str | None
    student_name: str
    branch_name: str
    academic_year: str
    year_level: str | None = None
    year_level_label: str | None = None
    programme_code: str | None = None
    programme_name: str | None
    programme_display: str | None = None
    section_name: str | None
    section_display: str | None = None


class FeeAccountCreateRequest(BaseModel):
    """Request to create the initial fee account for one enrollment."""

    enrollment_id: UUID
    assigned_fee_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    scholarship_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    concession_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    payment_schedule_type: PaymentScheduleType = "ONE_TIME"

    @model_validator(mode="after")
    def validate_net_amount(self) -> FeeAccountCreateRequest:
        if self.scholarship_amount + self.concession_amount > self.assigned_fee_amount:
            raise ValueError("Scholarship and concession cannot exceed assigned fee amount.")
        return self


class FeePaymentCreateRequest(BaseModel):
    """Request to post one received payment and generate a receipt entry."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    payment_mode: PaymentMode
    receipt_date: date
    external_reference: str | None = Field(default=None, max_length=180)
    payment_period_label: str | None = Field(default=None, max_length=80)
    installment_number: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=1000)


class FeePaymentPostResponse(BaseModel):
    """Response after a payment has been posted."""

    fee_account: FeeAccountListItem
    ledger_entry_id: UUID
    receipt_number: str


class FeeLedgerEntryItem(BaseModel):
    """One immutable fee ledger row for a fee account."""

    id: UUID
    entry_type: str
    balance_effect: str
    amount: Decimal
    payment_mode: str | None
    external_reference: str | None
    receipt_number: str | None
    receipt_date: date | None
    payment_period_label: str | None
    installment_number: int | None
    entry_date: date
    status: str
    notes: str | None
    collected_by_name: str | None
    posted_by_name: str | None
    posted_at: datetime
    created_at: datetime


class FeeLedgerResponse(BaseModel):
    """Fee account summary with its ledger history."""

    fee_account: FeeAccountListItem
    entries: list[FeeLedgerEntryItem]
