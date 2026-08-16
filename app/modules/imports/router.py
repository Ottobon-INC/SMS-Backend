# mypy: ignore-errors
# ruff: noqa: B008, E501

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database.session import get_db_session
from app.core.security.context import RequestContext
from app.core.security.dependencies import get_request_context, require_permission
from app.modules.imports.permissions import IMPORT_COMMIT, IMPORT_UPLOAD, IMPORT_VIEW_PREVIEW
from app.modules.imports.repository import ImportRepository
from app.modules.imports.schemas import (
    AcademicYearLookup,
    ActivatePortalResponse,
    BatchLookup,
    BulkActivateEligibilityResponse,
    BulkActivateSectionRequest,
    BulkActivateSectionResponse,
    ImportRowCorrectionRequest,
    ManualAddStudentRequest,
    ManualAddStudentResponse,
    PreviewResponse,
    ProgrammeLookup,
    SectionLookup,
    UploadResponse,
)
from app.modules.imports.service import ImportService

router = APIRouter(prefix="/imports/students", tags=["Imports"])
fee_router = APIRouter(prefix="/imports/fees", tags=["Imports"])


def get_import_service(session: Session = Depends(get_db_session)) -> ImportService:
    return ImportService(ImportRepository(session), session)


@router.get("/template")
def download_student_import_template(
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    content = service.generate_student_import_template(context.tenant_id, context.branch_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="student_import_template.xlsx"'},
    )


@fee_router.get("/template")
def download_fee_import_template(
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    content = service.generate_fee_import_template(context.tenant_id, context.branch_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="fee_import_template.xlsx"'},
    )


@fee_router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_fee_accounts(
    file: UploadFile = File(...),
    branch_id: UUID | None = Form(None),
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    if context.branch_id is not None and branch_id is not None and context.branch_id != branch_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this branch.")

    content = file.file.read()
    return service.upload_fee_excel(
        tenant_id=context.tenant_id,
        branch_id=branch_id,
        app_user_id=context.app_user_id,
        file_content=content,
        filename=file.filename or "fee_import.xlsx",
        context_branch_id=context.branch_id,
    )


@fee_router.get("/batches/{batch_id}/preview", response_model=PreviewResponse)
def get_fee_batch_preview(
    batch_id: UUID,
    context: RequestContext = Depends(require_permission(IMPORT_VIEW_PREVIEW)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.get_import_preview(batch_id, context.tenant_id, context.branch_id, expected_module_code="fees")


@fee_router.patch("/batches/{batch_id}/rows/{row_id}", response_model=PreviewResponse)
def correct_fee_batch_row(
    batch_id: UUID,
    row_id: UUID,
    payload: ImportRowCorrectionRequest,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.correct_fee_import_row(
        batch_id=batch_id,
        row_id=row_id,
        tenant_id=context.tenant_id,
        raw_data=payload.raw_data,
        context_branch_id=context.branch_id,
    )


@fee_router.post("/batches/{batch_id}/commit")
def commit_fee_import(
    batch_id: UUID,
    context: RequestContext = Depends(require_permission(IMPORT_COMMIT)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.commit_fee_import(batch_id, context.tenant_id, context.app_user_id, context.branch_id)


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
def upload_students(
    file: UploadFile = File(...),
    branch_id: UUID | None = Form(None),
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    
    # Enforce branch scope if user is limited and trying to override
    if context.branch_id is not None and branch_id is not None and context.branch_id != branch_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this branch.")

    content = file.file.read()
    return service.upload_student_excel(
        tenant_id=context.tenant_id,
        branch_id=branch_id,
        app_user_id=context.app_user_id,
        file_content=content,
        filename=file.filename or "upload.xlsx",
        context_branch_id=context.branch_id
    )


@router.get("/batches/{batch_id}/preview", response_model=PreviewResponse)
def get_batch_preview(
    batch_id: UUID,
    context: RequestContext = Depends(require_permission(IMPORT_VIEW_PREVIEW)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.get_import_preview(batch_id, context.tenant_id, context.branch_id, expected_module_code="students")


@router.patch("/batches/{batch_id}/rows/{row_id}", response_model=PreviewResponse)
def correct_batch_row(
    batch_id: UUID,
    row_id: UUID,
    payload: ImportRowCorrectionRequest,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.correct_import_row(
        batch_id=batch_id,
        row_id=row_id,
        tenant_id=context.tenant_id,
        raw_data=payload.raw_data,
        context_branch_id=context.branch_id,
    )


@router.post("/batches/{batch_id}/commit")
def commit_import(
    batch_id: UUID,
    context: RequestContext = Depends(require_permission(IMPORT_COMMIT)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.commit_student_import(batch_id, context.tenant_id, context.app_user_id, context.branch_id)


@router.post("/manual-student", response_model=ManualAddStudentResponse, status_code=status.HTTP_201_CREATED)
def manual_add_student(
    payload: ManualAddStudentRequest,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),  # Same permission as upload for now
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    
    # If the user is scoped to a specific branch, enforce it.
    if context.branch_id is not None and context.branch_id != payload.branch_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this branch.")

    result = service.create_manual_student(
        tenant_id=context.tenant_id,
        branch_id=payload.branch_id,
        app_user_id=context.app_user_id,
        payload=payload
    )
    return ManualAddStudentResponse(**result)


# --- Academic Lookups purely for Manual Add form ---

class BranchLookup(BaseModel):
    id: UUID
    name: str
    code: str

@router.get("/lookups/branches", response_model=list[BranchLookup])
def get_branches_lookup(
    context: RequestContext = Depends(get_request_context),
    service: ImportService = Depends(get_import_service)
):
    assert context.tenant_id is not None
    # If scoped to a specific branch, only return that one.
    if context.branch_id:
        from app.modules.branches.models import Branch
        branch = service.session.get(Branch, context.branch_id)
        if branch:
            return [{"id": branch.id, "name": branch.display_name, "code": branch.branch_code}]
        return []
    
    # Otherwise, return all branches in the tenant.
    from sqlalchemy import select

    from app.modules.branches.models import Branch
    stmt = select(Branch).where(Branch.tenant_id == context.tenant_id, Branch.status == 'ACTIVE')
    branches = service.session.scalars(stmt).all()
    return [{"id": b.id, "name": b.display_name, "code": b.branch_code} for b in branches]

@router.get("/lookups/academic-years", response_model=list[AcademicYearLookup])
def get_academic_years_lookup(
    context: RequestContext = Depends(get_request_context),
    service: ImportService = Depends(get_import_service)
):
    assert context.tenant_id is not None
    years = service.repository.get_academic_years(context.tenant_id)
    return [{"id": y.id, "name": y.name} for y in years]


@router.get("/lookups/programmes", response_model=list[ProgrammeLookup])
def get_programmes_lookup(
    context: RequestContext = Depends(get_request_context),
    service: ImportService = Depends(get_import_service)
):
    assert context.tenant_id is not None
    programmes = service.repository.get_programmes(context.tenant_id)
    return [{"id": p.id, "name": p.programme_name} for p in programmes]


@router.get("/lookups/batches", response_model=list[BatchLookup])
def get_batches_lookup(
    branch_id: UUID,
    academic_year_id: UUID | None = None,
    programme_id: UUID | None = None,
    context: RequestContext = Depends(get_request_context),
    service: ImportService = Depends(get_import_service)
):
    assert context.tenant_id is not None
    
    # Enforce scope if user is branch-limited
    target_branch_id = branch_id
    if context.branch_id is not None and context.branch_id != target_branch_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this branch.")
        
    batches = service.repository.get_batches(context.tenant_id, target_branch_id, academic_year_id, programme_id)
    return [{"id": b.id, "name": b.batch_name} for b in batches]


@router.get("/lookups/sections", response_model=list[SectionLookup])
def get_sections_lookup(
    batch_id: UUID,
    context: RequestContext = Depends(get_request_context),
    service: ImportService = Depends(get_import_service)
):
    assert context.tenant_id is not None
    assert context.branch_id is not None
    sections = service.repository.get_sections(context.tenant_id, context.branch_id, batch_id)
    return [{"id": s.id, "name": s.section_name} for s in sections]


# --- Parent Portal Activation Endpoints ---

@router.post("/guardians/{guardian_id}/activate-portal", response_model=ActivatePortalResponse)
def activate_parent_portal(
    guardian_id: UUID,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)), # Reusing upload/commit temporarily per MVP scope
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.activate_parent_portal(context.tenant_id, guardian_id, context.app_user_id)


@router.post("/guardians/activation-eligibility", response_model=BulkActivateEligibilityResponse)
def get_activation_eligibility(
    payload: BulkActivateSectionRequest,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.get_bulk_activation_eligibility(context.tenant_id, payload)


@router.post("/guardians/bulk-activate", response_model=BulkActivateSectionResponse)
def bulk_activate_parent_portal(
    payload: BulkActivateSectionRequest,
    context: RequestContext = Depends(require_permission(IMPORT_UPLOAD)),
    service: ImportService = Depends(get_import_service),
):
    assert context.tenant_id is not None
    return service.bulk_activate_parent_portal(context.tenant_id, payload, context.app_user_id)
