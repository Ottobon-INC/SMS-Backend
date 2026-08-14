import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.imports.repository import ImportRepository
from app.modules.imports.schemas import (
    AcademicYearLookup,
    BatchLookup,
    ManualAddStudentRequest,
    PreviewResponse,
    SectionLookup,
    UploadResponse,
    ActivatePortalResponse,
    BulkActivateSectionRequest,
    BulkActivateSectionResponse,
    BulkActivationResult,
    BulkActivateEligibilityResponse,
    ImportBatchResponse,
    ImportRowResult,
)
from app.modules.imports.validators import StudentImportValidator
from app.modules.students.models import Enrollment, Guardian, Student, StudentGuardianLink


class ImportService:
    def __init__(self, repository: ImportRepository, session: Session) -> None:
        self.repository = repository
        self.session = session

    def upload_student_excel(
        self, tenant_id: UUID, branch_id: UUID | None, app_user_id: UUID, file_content: bytes, filename: str, context_branch_id: UUID | None = None
    ) -> UploadResponse:
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        batch = ImportBatch(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            branch_id=branch_id,
            module_code="students",
            import_type="EXCEL_TEMPLATE",
            schema_version="V1",
            source_filename=filename,
            storage_key=f"imports/students/{file_hash}.xlsx",
            checksum=file_hash,
            idempotency_key=f"{tenant_id}-{file_hash}",
            status="UPLOADED",
            created_by=app_user_id,
        )
        self.repository.create_batch(batch)

        validator = StudentImportValidator(self.repository, tenant_id, context_branch_id)
        
        try:
            row_results, summary = validator.parse_and_validate(file_content)
        except ValueError as e:
            batch.status = "FAILED"
            self.repository.update_batch(batch)
            self.session.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        batch.summary = summary
        batch.status = "PREVIEW"
        self.repository.update_batch(batch)

        db_rows = []
        for res in row_results:
            db_row = ImportRow(
                id=uuid.uuid4(),
                batch_id=batch.id,
                row_number=res["row_number"],
                raw_data=res["raw_data"],
                normalized_data=res["normalized_data"],
                validation_status=res["validation_status"],
                errors=res["errors"],
                target_entity_type="Student",
            )
            db_rows.append(db_row)
            
        self.repository.create_rows(db_rows)
        self.session.commit()

        return UploadResponse(
            message="File uploaded and validated.",
            batch_id=batch.id,
            status=batch.status,
        )

    def get_import_preview(self, batch_id: UUID, tenant_id: UUID, context_branch_id: UUID | None) -> PreviewResponse:
        batch = self.repository.get_batch(batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
        if context_branch_id and batch.branch_id and batch.branch_id != context_branch_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this batch.")
            
        rows = self.repository.get_rows(batch_id)
        
        return PreviewResponse(
            batch=ImportBatchResponse.model_validate(batch),
            rows=[ImportRowResult.model_validate(r) for r in rows]
        )

    def commit_student_import(self, batch_id: UUID, tenant_id: UUID, app_user_id: UUID, context_branch_id: UUID | None) -> dict[str, Any]:
        batch = self.repository.get_batch(batch_id)
        if not batch or batch.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found.")
        if context_branch_id and batch.branch_id and batch.branch_id != context_branch_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this batch.")
            
        if batch.status not in ["PREVIEW", "SUBMITTED"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batch is not ready to commit.")
            
        rows = self.repository.get_rows(batch_id)
        
        # Check if any rejected rows exist
        if any(r.validation_status == "REJECTED" for r in rows):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot commit batch with REJECTED rows.")

        try:
            for row in rows:
                if row.validation_status in ["VALID", "WARNING"]:
                    data = row.normalized_data
                    if not data:
                        continue
                    student_id = uuid.uuid4()
                    enrollment_id = uuid.uuid4()
                    
                    student = Student(
                        id=student_id,
                        tenant_id=tenant_id,
                        student_number=self.repository.generate_student_number(tenant_id),
                        legal_name=data["student_name"],
                        display_name=data["student_name"],
                        date_of_birth=datetime.fromisoformat(data["date_of_birth"]).date() if data.get("date_of_birth") else None,
                        gender=data["gender"],
                        student_mobile=data.get("student_mobile"),
                        current_status="ACTIVE",
                        source_type="IMPORT",
                        created_by=app_user_id,
                    )
                    self.session.add(student)
                    
                    # Match or Create Guardian
                    from sqlalchemy import select
                    stmt = select(Guardian).where(getattr(Guardian, "tenant_id") == tenant_id, getattr(Guardian, "mobile") == data["guardian_mobile"])
                    guardian = self.session.scalars(stmt).first()
                    if not guardian:
                        guardian_id = uuid.uuid4()
                        guardian = Guardian(
                            id=guardian_id,
                            tenant_id=tenant_id,
                            full_name=data["guardian_name"],
                            mobile=data["guardian_mobile"],
                            verification_status="UNVERIFIED",
                            status="ACTIVE",
                            created_by=app_user_id,
                        )
                        self.session.add(guardian)
                    else:
                        guardian_id = guardian.id
                    
                    link = StudentGuardianLink(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        student_id=student_id,
                        guardian_id=guardian_id,
                        relationship_type=data["guardian_relationship"],
                        is_primary=True,
                        verification_status="PENDING",
                        status="ACTIVE",
                        created_by=app_user_id,
                    )
                    self.session.add(link)
                    
                    self.session.flush() # Force insert of Student and Guardian before Enrollment
                    
                    enrollment = Enrollment(
                        id=enrollment_id,
                        tenant_id=tenant_id,
                        student_id=student_id,
                        branch_id=UUID(data["branch_id"]) if data.get("branch_id") else None,
                        academic_year_id=UUID(data["academic_year_id"]) if data.get("academic_year_id") else None,
                        programme_id=UUID(data["programme_id"]) if data.get("programme_id") else None,
                        batch_id=UUID(data["batch_id"]) if data.get("batch_id") else None,
                        section_id=UUID(data["section_id"]) if data.get("section_id") else None,
                        admission_number=data["admission_number"],
                        roll_number=data.get("roll_number"),
                        year_level=data["year_level"],
                        status="ACTIVE",
                        joining_date=datetime.fromisoformat(data["joining_date"]).date() if data.get("joining_date") else None,
                        is_current=True,
                        source_type="IMPORT",
                        created_by=app_user_id,
                    )
                    self.session.add(enrollment)
                    
                    row.target_entity_id = student_id

            batch.status = "COMMITTED"
            batch.committed_at = datetime.now(timezone.utc)
            self.session.commit()
            
            return {"message": "Batch committed successfully", "batch_id": batch.id}
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to commit batch: {str(e)}")

    def create_manual_student(
        self, tenant_id: UUID, branch_id: UUID, app_user_id: UUID, payload: "ManualAddStudentRequest"
    ) -> dict[str, Any]:
        # 1. Scope Validation & Academic Validation
        from app.modules.academic_structure.models import Section, Batch
        section = self.session.get(Section, payload.section_id)
        if not section or section.batch_id != payload.batch_id or section.tenant_id != tenant_id or section.branch_id != branch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid academic hierarchy: Section does not belong to the selected Batch/Branch.")
            
        batch_model = self.session.get(Batch, payload.batch_id)
        if not batch_model or batch_model.programme_id != payload.programme_id or batch_model.academic_year_id != payload.academic_year_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid academic hierarchy: Batch does not belong to the selected Programme/Academic Year.")
        
        # 2. Duplicate Checks
        if self.repository.check_admission_number_exists(tenant_id, branch_id, payload.admission_number):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Admission number already exists in this branch.")
            
        # 3. Generate Student Number
        student_number = self.repository.generate_student_number(tenant_id)
            
        try:
            # 4. Create Student
            student_id = uuid.uuid4()
            student = Student(
                id=student_id,
                tenant_id=tenant_id,
                student_number=student_number,
                legal_name=payload.student_name,
                display_name=payload.student_name,
                date_of_birth=payload.date_of_birth,
                gender=payload.gender,
                current_status="ACTIVE",
                source_type="MANUAL",
                created_by=app_user_id,
            )
            self.session.add(student)
            
            # 5. Match/Create Guardian
            # Lookup guardian by mobile in tenant
            # Here we assume a repo method get_guardian_by_mobile exists, or we just create a new one for MVP
            from sqlalchemy import select
            stmt = select(Guardian).where(getattr(Guardian, "tenant_id") == tenant_id, getattr(Guardian, "mobile") == payload.guardian_mobile)
            guardian = self.session.scalars(stmt).first()
            if not guardian:
                guardian_id = uuid.uuid4()
                guardian = Guardian(
                    id=guardian_id,
                    tenant_id=tenant_id,
                    full_name=payload.guardian_name,
                    mobile=payload.guardian_mobile,
                    email=payload.guardian_email,
                    verification_status="UNVERIFIED",
                    status="ACTIVE",
                    created_by=app_user_id,
                )
                self.session.add(guardian)
            else:
                guardian_id = guardian.id
                
            # 6. Create Guardian Link
            link = StudentGuardianLink(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                student_id=student_id,
                guardian_id=guardian_id,
                relationship_type=payload.relationship_type,
                is_primary=True,
                verification_status="PENDING",
                status="ACTIVE",
                created_by=app_user_id,
            )
            self.session.add(link)
            
            self.session.flush() # Force insert before Enrollment
            
            # 7. Create Enrolment
            enrollment_id = uuid.uuid4()
            enrollment = Enrollment(
                id=enrollment_id,
                tenant_id=tenant_id,
                student_id=student_id,
                branch_id=branch_id,
                academic_year_id=payload.academic_year_id,
                programme_id=payload.programme_id,
                batch_id=payload.batch_id,
                section_id=payload.section_id,
                admission_number=payload.admission_number,
                roll_number=payload.roll_number if payload.roll_number else None,
                year_level=payload.year_level,
                status="ACTIVE",
                joining_date=datetime.now(timezone.utc).date(),
                is_current=True,
                source_type="MANUAL",
                created_by=app_user_id,
            )
            self.session.add(enrollment)
            
            # 8. Commit
            self.session.commit()
            
            return {
                "student_id": student_id,
                "student_number": student_number,
                "guardian_id": guardian_id,
                "enrollment_id": enrollment_id
            }
        except Exception as e:
            self.session.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Transaction failed: {str(e)}")

    def activate_parent_portal(self, tenant_id: UUID, guardian_id: UUID, app_user_id: UUID) -> ActivatePortalResponse:
        """
        Orchestration contract for single guardian activation.
        Currently blocked by external dependency.
        """
        guardian = self.repository.get_guardian_with_links(guardian_id, tenant_id)
        if not guardian:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Guardian not found or inactive")
        
        # If already active, just return success
        if guardian.portal_user_id:
            return ActivatePortalResponse(
                guardian_id=guardian.id,
                portal_user_id=guardian.portal_user_id,
                status="ALREADY_ACTIVE",
                message="Parent Portal is already active for this guardian."
            )
            
        # External Dependency Block
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, 
            detail="External Dependency — Parent Account Provisioning Service"
        )

    def get_bulk_activation_eligibility(self, tenant_id: UUID, payload: BulkActivateSectionRequest) -> BulkActivateEligibilityResponse:
        """
        Calculates eligibility preview for bulk activation.
        """
        guardians = self.repository.get_guardians_for_section(
            tenant_id=tenant_id,
            branch_id=payload.branch_id,
            academic_year_id=payload.academic_year_id,
            programme_id=payload.programme_id,
            batch_id=payload.batch_id,
            section_id=payload.section_id
        )
        
        total_students = 0 # Handled externally or mock
        unique_guardians = len(guardians)
        already_active_count = sum(1 for g in guardians if g.portal_user_id is not None)
        missing_contact_count = sum(1 for g in guardians if not g.mobile and not g.email)
        eligible_count = unique_guardians - already_active_count - missing_contact_count
        
        return BulkActivateEligibilityResponse(
            total_students=total_students,
            unique_guardians=unique_guardians,
            eligible_count=eligible_count,
            already_active_count=already_active_count,
            missing_contact_count=missing_contact_count
        )

    def bulk_activate_parent_portal(self, tenant_id: UUID, payload: BulkActivateSectionRequest, app_user_id: UUID) -> BulkActivateSectionResponse:
        """
        Orchestration contract for bulk activation by section.
        Currently blocked by external dependency.
        """
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED, 
            detail="External Dependency — Parent Account Provisioning Service"
        )
