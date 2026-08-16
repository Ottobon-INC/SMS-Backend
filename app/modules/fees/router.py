# ruff: noqa: B008
"""Fee module API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.dependencies import require_permission
from app.modules.fees.permissions import FEE_BASIC_ASSIGN, FEE_PAYMENT_RECORD, FEE_VIEW
from app.modules.fees.repository import FeeRepository
from app.modules.fees.schemas import (
    FeeAccountCreateRequest,
    FeeAccountListItem,
    FeeEnrollmentOption,
    FeeLedgerResponse,
    FeePaymentCreateRequest,
    FeePaymentPostResponse,
)
from app.modules.fees.service import FeeService

router = APIRouter(prefix="/fees", tags=["Fees"])


def get_fee_service(session: Session = Depends(get_db_session)) -> FeeService:
    return FeeService(FeeRepository(session))


@router.get("/accounts", response_model=list[FeeAccountListItem])
def list_fee_accounts(
    context: RequestContext = Depends(require_permission(FEE_VIEW)),
    service: FeeService = Depends(get_fee_service),
) -> list[FeeAccountListItem]:
    """List fee accounts visible to the active tenant/branch context."""

    assert context.tenant_id is not None
    return service.list_fee_accounts(tenant_id=context.tenant_id, branch_id=context.branch_id)


@router.get("/setup-options", response_model=list[FeeEnrollmentOption])
def list_fee_setup_options(
    context: RequestContext = Depends(require_permission(FEE_BASIC_ASSIGN)),
    service: FeeService = Depends(get_fee_service),
) -> list[FeeEnrollmentOption]:
    """List active enrollments that do not yet have a fee account."""

    assert context.tenant_id is not None
    return service.list_fee_setup_options(tenant_id=context.tenant_id, branch_id=context.branch_id)


@router.post("/accounts", response_model=FeeAccountListItem, status_code=201)
def create_fee_account(
    payload: FeeAccountCreateRequest,
    context: RequestContext = Depends(require_permission(FEE_BASIC_ASSIGN)),
    service: FeeService = Depends(get_fee_service),
) -> FeeAccountListItem:
    """Create the initial fee account for one active enrollment."""

    assert context.tenant_id is not None
    return service.create_fee_account(
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        app_user_id=context.app_user_id,
        payload=payload,
    )


@router.get("/accounts/{account_id}/ledger", response_model=FeeLedgerResponse)
def get_fee_ledger(
    account_id: UUID,
    context: RequestContext = Depends(require_permission(FEE_VIEW)),
    service: FeeService = Depends(get_fee_service),
) -> FeeLedgerResponse:
    """Return the immutable ledger rows for one scoped fee account."""

    assert context.tenant_id is not None
    return service.get_fee_ledger(
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        account_id=account_id,
    )


@router.post(
    "/accounts/{account_id}/payments",
    response_model=FeePaymentPostResponse,
    status_code=201,
)
def post_fee_payment(
    account_id: UUID,
    payload: FeePaymentCreateRequest,
    context: RequestContext = Depends(require_permission(FEE_PAYMENT_RECORD)),
    service: FeeService = Depends(get_fee_service),
) -> FeePaymentPostResponse:
    """Post one payment and create a receipt ledger entry."""

    assert context.tenant_id is not None
    return service.post_payment(
        tenant_id=context.tenant_id,
        branch_id=context.branch_id,
        app_user_id=context.app_user_id,
        account_id=account_id,
        payload=payload,
    )
