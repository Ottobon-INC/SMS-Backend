from collections.abc import Sequence
from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.academic_structure.models import AcademicProgramme, AcademicYear, Batch, Section
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.students.models import Enrollment, Student, Guardian, StudentGuardianLink


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_batch(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(batch)
        self.session.flush()
        return batch

    def get_batch(self, batch_id: UUID) -> ImportBatch | None:
        return self.session.get(ImportBatch, batch_id)

    def update_batch(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(batch)
        self.session.flush()
        return batch

    def create_rows(self, rows: list[ImportRow]) -> list[ImportRow]:
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def get_rows(self, batch_id: UUID) -> Sequence[ImportRow]:
        stmt = select(ImportRow).where(ImportRow.batch_id == batch_id).order_by(ImportRow.row_number)
        return self.session.scalars(stmt).all()

    def resolve_branch(self, tenant_id: UUID, code: str) -> Any | None:
        from app.modules.branches.models import Branch
        stmt = select(Branch).where(
            Branch.tenant_id == tenant_id,
            (Branch.branch_code == code) | (Branch.display_name == code)
        )
        return self.session.scalars(stmt).first()

    def resolve_academic_year(self, tenant_id: UUID, year_name: str) -> AcademicYear | None:
        stmt = select(AcademicYear).where(
            AcademicYear.tenant_id == tenant_id,
            (AcademicYear.name == year_name) | (AcademicYear.code == year_name)
        )
        return self.session.scalars(stmt).first()

    def resolve_programme(self, tenant_id: UUID, name: str) -> AcademicProgramme | None:
        stmt = select(AcademicProgramme).where(
            AcademicProgramme.tenant_id == tenant_id,
            (AcademicProgramme.programme_name == name) | (AcademicProgramme.programme_code == name)
        )
        return self.session.scalars(stmt).first()

    def resolve_batch(
        self, tenant_id: UUID, branch_id: UUID, academic_year_id: UUID, programme_id: UUID, name: str
    ) -> Batch | None:
        stmt = select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.branch_id == branch_id,
            Batch.academic_year_id == academic_year_id,
            Batch.programme_id == programme_id,
            (Batch.batch_name == name) | (Batch.batch_code == name)
        )
        return self.session.scalars(stmt).first()

    def resolve_section(self, tenant_id: UUID, branch_id: UUID, batch_id: UUID, name: str) -> Section | None:
        stmt = select(Section).where(
            Section.tenant_id == tenant_id,
            Section.branch_id == branch_id,
            Section.batch_id == batch_id,
            (Section.section_name == name) | (Section.section_code == name)
        )
        return self.session.scalars(stmt).first()

    def check_student_number_exists(self, tenant_id: UUID, student_number: str) -> bool:
        stmt = select(Student.id).where(
            Student.tenant_id == tenant_id,
            Student.student_number == student_number
        )
        return self.session.scalars(stmt).first() is not None

    def generate_student_number(self, tenant_id: UUID) -> str:
        import uuid
        student_number = f"STU-{uuid.uuid4().hex[:8].upper()}"
        while self.check_student_number_exists(tenant_id, student_number):
            student_number = f"STU-{uuid.uuid4().hex[:8].upper()}"
        return student_number

    def check_admission_number_exists(self, tenant_id: UUID, branch_id: UUID, admission_number: str) -> bool:
        stmt = select(Enrollment.id).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.branch_id == branch_id,
            Enrollment.admission_number == admission_number
        )
        return self.session.scalars(stmt).first() is not None

    def get_academic_years(self, tenant_id: UUID) -> Sequence[AcademicYear]:
        stmt = select(AcademicYear).where(
            AcademicYear.tenant_id == tenant_id,
            AcademicYear.status == 'ACTIVE'
        ).order_by(AcademicYear.starts_on.desc())
        return self.session.scalars(stmt).all()

    def get_programmes(self, tenant_id: UUID) -> Sequence[AcademicProgramme]:
        stmt = select(AcademicProgramme).where(
            AcademicProgramme.tenant_id == tenant_id,
            AcademicProgramme.status == 'ACTIVE'
        ).order_by(AcademicProgramme.programme_name)
        return self.session.scalars(stmt).all()

    def get_batches(self, tenant_id: UUID, branch_id: UUID, academic_year_id: UUID | None = None, programme_id: UUID | None = None) -> Sequence[Batch]:
        stmt = select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.branch_id == branch_id,
            Batch.status == 'ACTIVE'
        )
        if academic_year_id:
            stmt = stmt.where(Batch.academic_year_id == academic_year_id)
        if programme_id:
            stmt = stmt.where(Batch.programme_id == programme_id)
        stmt = stmt.order_by(Batch.batch_name)
        return self.session.scalars(stmt).all()

    def get_sections(self, tenant_id: UUID, branch_id: UUID, batch_id: UUID) -> Sequence[Section]:
        stmt = select(Section).where(
            Section.tenant_id == tenant_id,
            Section.branch_id == branch_id,
            Section.batch_id == batch_id,
            Section.status == 'ACTIVE'
        ).order_by(Section.section_name)
        return self.session.scalars(stmt).all()

    def get_guardian_with_links(self, guardian_id: UUID, tenant_id: UUID) -> Guardian | None:
        """Fetch a guardian and ensure they belong to the tenant and have active student links."""
        stmt = select(Guardian).where(
            Guardian.id == guardian_id,
            Guardian.tenant_id == tenant_id,
            Guardian.status == 'ACTIVE'
        )
        return self.session.scalars(stmt).first()

    def get_guardians_for_section(
        self, tenant_id: UUID, branch_id: UUID, academic_year_id: UUID, programme_id: UUID | None, batch_id: UUID | None, section_id: UUID
    ) -> Sequence[Guardian]:
        """Fetch all unique, active guardians connected to students in a specific section."""
        stmt = select(Guardian).distinct().join(
            StudentGuardianLink, Guardian.id == StudentGuardianLink.guardian_id
        ).join(
            Student, StudentGuardianLink.student_id == Student.id
        ).join(
            Enrollment, Student.id == Enrollment.student_id
        ).where(
            Guardian.tenant_id == tenant_id,
            Guardian.status == 'ACTIVE',
            StudentGuardianLink.status == 'ACTIVE',
            Enrollment.tenant_id == tenant_id,
            Enrollment.branch_id == branch_id,
            Enrollment.academic_year_id == academic_year_id,
            Enrollment.section_id == section_id,
            Enrollment.status == 'ACTIVE',
            Enrollment.is_current == True
        )
        if programme_id:
            stmt = stmt.where(Enrollment.programme_id == programme_id)
        if batch_id:
            stmt = stmt.where(Enrollment.batch_id == batch_id)
            
        return self.session.scalars(stmt).all()

    def enable_portal_access_for_links(self, guardian_id: UUID, tenant_id: UUID) -> None:
        """Enable portal access for all active links for a guardian."""
        from sqlalchemy import update
        stmt = update(StudentGuardianLink).where(
            StudentGuardianLink.guardian_id == guardian_id,
            StudentGuardianLink.tenant_id == tenant_id,
            StudentGuardianLink.status == 'ACTIVE'
        ).values(portal_access_enabled=True)
        self.session.execute(stmt)
        self.session.flush()
