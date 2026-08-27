# ruff: noqa: E501, E712

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.modules.academic_structure.models import AcademicProgramme, AcademicYear, Batch, Section
from app.modules.academic_structure.constants import normalize_programme_match_value, programme_display_label
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.students.models import Enrollment, Guardian, Student, StudentGuardianLink


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_batch(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(batch)
        self.session.flush()
        return batch

    def get_batch(self, batch_id: UUID) -> ImportBatch | None:
        return self.session.get(ImportBatch, batch_id)

    def get_batch_by_idempotency_key(self, tenant_id: UUID, idempotency_key: str) -> ImportBatch | None:
        stmt = select(ImportBatch).where(
            ImportBatch.tenant_id == tenant_id,
            ImportBatch.idempotency_key == idempotency_key,
        )
        return self.session.scalars(stmt).first()

    def update_batch(self, batch: ImportBatch) -> ImportBatch:
        self.session.add(batch)
        self.session.flush()
        return batch

    def create_rows(self, rows: list[ImportRow]) -> list[ImportRow]:
        self.session.add_all(rows)
        self.session.flush()
        return rows

    def delete_rows_for_batch(self, batch_id: UUID) -> None:
        self.session.execute(delete(ImportRow).where(ImportRow.batch_id == batch_id))
        self.session.flush()

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

    def resolve_programme(self, tenant_id: UUID, name: str) -> Any | None:
        normalized_name = normalize_programme_match_value(name)
        rows = self.session.execute(
            text("""
                SELECT
                    *,
                    CASE
                        WHEN stream_code IS NOT NULL AND coaching_track IS NOT NULL
                            THEN stream_code || ' - ' || coaching_track
                        WHEN programme_code IS NOT NULL
                            AND programme_name IS NOT NULL
                            AND programme_name NOT ILIKE programme_code || ' - %'
                            THEN programme_code || ' - ' || programme_name
                        ELSE COALESCE(programme_name, programme_code)
                    END AS display_label
                FROM sms_academic_programmes
                WHERE tenant_id = :tenant_id
                    AND status = 'ACTIVE'
                ORDER BY programme_code
            """),
            {"tenant_id": tenant_id},
        ).fetchall()
        for row in rows:
            candidates = {
                row.programme_code,
                row.programme_name,
                row.stream_code,
                row.coaching_track,
                row.display_label,
                programme_display_label(
                    programme_code=row.programme_code,
                    programme_name=row.programme_name,
                    stream_code=row.stream_code,
                    coaching_track=row.coaching_track,
                ),
            }
            if row.stream_code and row.coaching_track:
                candidates.add(f"{row.stream_code} {row.coaching_track}")
                candidates.add(f"{row.stream_code}-{row.coaching_track}")
            if normalized_name in {normalize_programme_match_value(candidate) for candidate in candidates if candidate}:
                return row
        return None

    def resolve_batch(
        self, tenant_id: UUID, branch_id: UUID, academic_year_id: UUID, programme_id: UUID, name: str
    ) -> Batch | None:
        normalized_name = name.strip()
        stmt = select(Batch).where(
            Batch.tenant_id == tenant_id,
            Batch.branch_id == branch_id,
            Batch.academic_year_id == academic_year_id,
            Batch.programme_id == programme_id,
            (func.lower(Batch.batch_name) == normalized_name.lower())
            | (func.lower(Batch.batch_code) == normalized_name.lower()),
        )
        return self.session.scalars(stmt).first()

    def resolve_section(self, tenant_id: UUID, branch_id: UUID, batch_id: UUID, name: str) -> Section | None:
        normalized_name = name.strip()
        stmt = select(Section).where(
            Section.tenant_id == tenant_id,
            Section.branch_id == branch_id,
            Section.batch_id == batch_id,
            (func.lower(Section.section_name) == normalized_name.lower())
            | (func.lower(Section.section_code) == normalized_name.lower()),
        )
        return self.session.scalars(stmt).first()

    def resolve_section_placement(
        self,
        tenant_id: UUID,
        branch_id: UUID,
        academic_year_id: UUID,
        programme_id: UUID,
        section_name_or_code: str,
        batch_name_or_code: str | None = None,
        year_level: str | None = None,
    ) -> Any | None:
        return self.session.execute(
            text("""
                SELECT
                    s.id AS section_id,
                    bt.id AS batch_id,
                    bt.year_level
                FROM sms_sections s
                JOIN sms_batches bt
                    ON bt.tenant_id = s.tenant_id
                    AND bt.branch_id = s.branch_id
                    AND bt.id = s.batch_id
                WHERE s.tenant_id = :tenant_id
                    AND s.branch_id = :branch_id
                    AND bt.academic_year_id = :academic_year_id
                    AND bt.programme_id = :programme_id
                    AND s.status = 'ACTIVE'
                    AND bt.status = 'ACTIVE'
                    AND (
                        CAST(:batch_value AS text) IS NULL
                        OR lower(bt.batch_name) = lower(CAST(:batch_value AS text))
                        OR lower(bt.batch_code) = lower(CAST(:batch_value AS text))
                    )
                    AND (
                        CAST(:year_level AS text) IS NULL
                        OR bt.year_level = CAST(:year_level AS text)
                    )
                    AND (
                        lower(s.section_name) = lower(CAST(:section_value AS text))
                        OR lower(s.section_code) = lower(CAST(:section_value AS text))
                    )
                ORDER BY s.section_name
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "academic_year_id": academic_year_id,
                "programme_id": programme_id,
                "section_value": section_name_or_code,
                "batch_value": batch_name_or_code or None,
                "year_level": year_level or None,
            },
        ).fetchone()

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

    def check_roll_number_exists(self, tenant_id: UUID, branch_id: UUID, academic_year_id: UUID, roll_number: str) -> bool:
        stmt = select(Enrollment.id).where(
            Enrollment.tenant_id == tenant_id,
            Enrollment.branch_id == branch_id,
            Enrollment.academic_year_id == academic_year_id,
            Enrollment.roll_number == roll_number
        )
        return self.session.scalars(stmt).first() is not None

    def possible_student_match_exists(
        self,
        tenant_id: UUID,
        student_name: str,
        date_of_birth: str,
        guardian_mobile: str,
    ) -> bool:
        row = self.session.execute(
            text("""
                SELECT 1
                FROM sms_students s
                JOIN sms_student_guardian_links sgl
                    ON sgl.tenant_id = s.tenant_id
                    AND sgl.student_id = s.id
                    AND sgl.status = 'ACTIVE'
                JOIN sms_guardians g
                    ON g.tenant_id = sgl.tenant_id
                    AND g.id = sgl.guardian_id
                WHERE s.tenant_id = :tenant_id
                    AND lower(s.legal_name) = lower(:student_name)
                    AND s.date_of_birth = CAST(:date_of_birth AS date)
                    AND g.mobile = :guardian_mobile
                LIMIT 1
            """),
            {
                "tenant_id": tenant_id,
                "student_name": student_name,
                "date_of_birth": date_of_birth,
                "guardian_mobile": guardian_mobile,
            },
        ).first()
        return row is not None

    def get_academic_years(self, tenant_id: UUID) -> Sequence[AcademicYear]:
        stmt = select(AcademicYear).where(
            AcademicYear.tenant_id == tenant_id,
            AcademicYear.status == 'ACTIVE'
        ).order_by(AcademicYear.starts_on.desc())
        return self.session.scalars(stmt).all()

    def get_programmes(
        self,
        tenant_id: UUID,
        branch_id: UUID | None = None,
        academic_year_id: UUID | None = None,
    ) -> Sequence[AcademicProgramme]:
        stmt = select(AcademicProgramme).where(
            AcademicProgramme.tenant_id == tenant_id,
            AcademicProgramme.status == 'ACTIVE'
        )
        if branch_id:
            stmt = stmt.join(
                Batch,
                (Batch.tenant_id == AcademicProgramme.tenant_id)
                & (Batch.programme_id == AcademicProgramme.id),
            ).where(
                Batch.branch_id == branch_id,
                Batch.status == 'ACTIVE',
            )
            if academic_year_id:
                stmt = stmt.where(Batch.academic_year_id == academic_year_id)
            stmt = stmt.distinct()
        stmt = stmt.order_by(AcademicProgramme.programme_name)
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

    def get_sections(self, tenant_id: UUID, branch_id: UUID | None, batch_id: UUID) -> Sequence[Section]:
        stmt = select(Section).where(
            Section.tenant_id == tenant_id,
            Section.batch_id == batch_id,
            Section.status == 'ACTIVE'
        )
        if branch_id:
            stmt = stmt.where(Section.branch_id == branch_id)
        stmt = stmt.order_by(Section.section_name)
        return self.session.scalars(stmt).all()

    def find_fee_import_enrollments(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID | None,
        admission_number: str,
        academic_year: str,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            text("""
                SELECT
                    e.id AS enrollment_id,
                    e.student_id,
                    e.branch_id,
                    e.academic_year_id,
                    e.admission_number,
                    s.legal_name,
                    s.display_name,
                    ay.name AS academic_year,
                    ap.programme_code,
                    ap.programme_name,
                    ap.stream_code,
                    ap.coaching_track,
                    CASE
                        WHEN ap.stream_code IS NOT NULL AND ap.coaching_track IS NOT NULL
                            THEN ap.stream_code || ' - ' || ap.coaching_track
                        WHEN ap.programme_code IS NOT NULL
                            AND ap.programme_name IS NOT NULL
                            AND ap.programme_name NOT ILIKE ap.programme_code || ' - %'
                            THEN ap.programme_code || ' - ' || ap.programme_name
                        ELSE COALESCE(ap.programme_name, ap.programme_code)
                    END AS programme_display,
                    sec.section_name,
                    fa.id AS fee_account_id
                FROM sms_enrollments e
                JOIN sms_students s
                    ON s.tenant_id = e.tenant_id
                    AND s.id = e.student_id
                JOIN sms_academic_years ay
                    ON ay.tenant_id = e.tenant_id
                    AND ay.id = e.academic_year_id
                LEFT JOIN sms_academic_programmes ap
                    ON ap.tenant_id = e.tenant_id
                    AND ap.id = e.programme_id
                LEFT JOIN sms_sections sec
                    ON sec.tenant_id = e.tenant_id
                    AND sec.branch_id = e.branch_id
                    AND sec.batch_id = e.batch_id
                    AND sec.id = e.section_id
                LEFT JOIN sms_fee_accounts fa
                    ON fa.tenant_id = e.tenant_id
                    AND fa.enrollment_id = e.id
                WHERE e.tenant_id = :tenant_id
                    AND lower(e.admission_number) = lower(:admission_number)
                    AND (lower(ay.name) = lower(:academic_year) OR lower(ay.code) = lower(:academic_year))
                    AND e.status = 'ACTIVE'
                    AND e.is_current = true
                    AND s.current_status = 'ACTIVE'
                    AND (CAST(:branch_id AS uuid) IS NULL OR e.branch_id = CAST(:branch_id AS uuid))
                ORDER BY e.created_at DESC
            """),
            {
                "tenant_id": tenant_id,
                "branch_id": str(branch_id) if branch_id else None,
                "admission_number": admission_number,
                "academic_year": academic_year,
            },
        ).mappings().all()
        return [dict(row) for row in rows]

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
