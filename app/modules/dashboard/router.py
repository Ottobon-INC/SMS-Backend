"""Dashboard module routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.dependencies import require_enabled_module
from app.modules.dashboard.repository import DashboardRepository
from app.modules.dashboard.schemas import InstitutionDashboardResponse, OfficeStaffDashboardResponse
from app.modules.dashboard.service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
dashboard_context_dependency = require_enabled_module("dashboard")


@router.get("/office-staff", response_model=OfficeStaffDashboardResponse)
def get_office_staff_dashboard(
    session: Annotated[Session, Depends(get_db_session)],
    context: Annotated[RequestContext, Depends(dashboard_context_dependency)],
    branch_id: UUID | None = None,
) -> OfficeStaffDashboardResponse:
    """Return the branch-scoped Office Staff operational dashboard."""

    return DashboardService(DashboardRepository(session)).get_office_staff_dashboard(context, branch_id)


@router.get("/institution", response_model=InstitutionDashboardResponse)
def get_institution_dashboard(
    session: Annotated[Session, Depends(get_db_session)],
    context: Annotated[RequestContext, Depends(dashboard_context_dependency)],
) -> InstitutionDashboardResponse:
    """Return the tenant-scoped Institution dashboard."""

    return DashboardService(DashboardRepository(session)).get_institution_dashboard(context)
