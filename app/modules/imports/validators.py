# ruff: noqa: E501

import io
from datetime import date, datetime
from typing import Any
from uuid import UUID

import openpyxl

from app.modules.imports.repository import ImportRepository


class StudentImportValidator:
    def __init__(self, repository: ImportRepository, tenant_id: UUID, context_branch_id: UUID | None = None) -> None:
        self.repository = repository
        self.tenant_id = tenant_id
        self.context_branch_id = context_branch_id
        self.required_columns = [
            "Branch Code",
            "Admission Number",
            "Student Full Name",
            "Date of Birth",
            "Gender",
            "Guardian Name",
            "Guardian Relationship",
            "Guardian Mobile",
            "Year Level",
            "Programme / Stream",
            "Batch",
            "Section",
            "Joining Date",
            "Academic Year",
        ]

    def parse_and_validate(self, file_content: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        wb = openpyxl.load_workbook(io.BytesIO(file_content), data_only=True)
        sheet = wb.active
        if not sheet:
            raise ValueError("No active sheet found in Excel file.")

        rows_iter = sheet.iter_rows(values_only=True)
        headers = next(rows_iter, None)
        if not headers:
            raise ValueError("Excel file is empty.")

        header_map = {str(h).strip(): i for i, h in enumerate(headers) if h is not None}
        missing_headers = [col for col in self.required_columns if col not in header_map]
        if missing_headers:
            raise ValueError(f"Missing required columns: {', '.join(missing_headers)}")

        results = []
        summary = {"total_rows": 0, "valid_rows": 0, "warning_rows": 0, "rejected_rows": 0}

        for row_idx, row_values in enumerate(rows_iter, start=2):
            # Skip completely empty rows
            if not any(row_values):
                continue
            
            summary["total_rows"] += 1

            raw_data = {
                header: row_values[idx] for header, idx in header_map.items()
            }
            normalized_data = {}
            errors = []
            status = "VALID"

            # Basic extraction
            branch_code = str(raw_data.get("Branch Code") or "").strip()
            admission_number = str(raw_data.get("Admission Number") or "").strip()
            student_name = str(raw_data.get("Student Full Name") or "").strip()
            dob = raw_data.get("Date of Birth")
            gender = str(raw_data.get("Gender") or "").strip().upper()
            guardian_name = str(raw_data.get("Guardian Name") or "").strip()
            guardian_rel = str(raw_data.get("Guardian Relationship") or "").strip().upper()
            guardian_mobile = str(raw_data.get("Guardian Mobile") or "").strip()
            year_level = str(raw_data.get("Year Level") or "").strip()
            programme_str = str(raw_data.get("Programme / Stream") or "").strip()
            batch_str = str(raw_data.get("Batch") or "").strip()
            section_str = str(raw_data.get("Section") or "").strip()
            joining_date = raw_data.get("Joining Date")
            academic_year_str = str(raw_data.get("Academic Year") or "").strip()
            roll_number = str(raw_data.get("Roll Number") or "").strip()
            student_mobile = str(raw_data.get("Student Mobile") or "").strip()

            # Date parsing
            if isinstance(dob, datetime):
                dob_val = dob.date().isoformat()
            elif isinstance(dob, date):
                dob_val = dob.isoformat()
            else:
                errors.append({"field": "Date of Birth", "message": "Invalid date format."})
                status = "REJECTED"
                dob_val = None

            if isinstance(joining_date, datetime):
                joining_val = joining_date.date().isoformat()
            elif isinstance(joining_date, date):
                joining_val = joining_date.isoformat()
            else:
                errors.append({"field": "Joining Date", "message": "Invalid date format."})
                status = "REJECTED"
                joining_val = None

            # Required fields check
            if not admission_number:
                errors.append({"field": "Admission Number", "message": "Required field missing."})
                status = "REJECTED"
            if not student_name:
                errors.append({"field": "Student Full Name", "message": "Required field missing."})
                status = "REJECTED"
            if not guardian_name:
                errors.append({"field": "Guardian Name", "message": "Required field missing."})
                status = "REJECTED"
            if not guardian_mobile:
                errors.append({"field": "Guardian Mobile", "message": "Required field missing."})
                status = "REJECTED"
            
            # Guardian Relationship validation
            valid_relations = ["FATHER", "MOTHER", "LEGAL_GUARDIAN", "RELATIVE", "SPONSOR", "OTHER"]
            if guardian_rel not in valid_relations:
                errors.append({"field": "Guardian Relationship", "message": f"Must be one of {valid_relations}"})
                status = "REJECTED"

            # Academic Resolution
            row_branch_id = None
            if not branch_code:
                errors.append({"field": "Branch Code", "message": "Required field missing."})
                status = "REJECTED"
            else:
                resolved_branch = self.repository.resolve_branch(self.tenant_id, branch_code)
                if not resolved_branch:
                    errors.append({"field": "Branch Code", "message": f"Not found: {branch_code}"})
                    status = "REJECTED"
                else:
                    row_branch_id = resolved_branch.id
                    if self.context_branch_id and row_branch_id != self.context_branch_id:
                        errors.append({"field": "Branch Code", "message": f"Unauthorized branch: {branch_code}"})
                        status = "REJECTED"

            academic_year_id = None
            if academic_year_str:
                ay = self.repository.resolve_academic_year(self.tenant_id, academic_year_str)
                if not ay:
                    errors.append({"field": "Academic Year", "message": f"Not found: {academic_year_str}"})
                    status = "REJECTED"
                else:
                    academic_year_id = ay.id

            programme_id = None
            if programme_str:
                prog = self.repository.resolve_programme(self.tenant_id, programme_str)
                if not prog:
                    errors.append({"field": "Programme / Stream", "message": f"Not found: {programme_str}"})
                    status = "REJECTED"
                else:
                    programme_id = prog.id

            batch_id = None
            if batch_str and academic_year_id and programme_id and row_branch_id:
                batch = self.repository.resolve_batch(self.tenant_id, row_branch_id, academic_year_id, programme_id, batch_str)
                if not batch:
                    errors.append({"field": "Batch", "message": f"Not found: {batch_str} (in selected programme/year/branch)"})
                    status = "REJECTED"
                else:
                    batch_id = batch.id

            section_id = None
            if section_str and batch_id and row_branch_id:
                section = self.repository.resolve_section(self.tenant_id, row_branch_id, batch_id, section_str)
                if not section:
                    errors.append({"field": "Section", "message": f"Not found: {section_str} (in selected batch)"})
                    status = "REJECTED"
                else:
                    section_id = section.id

            # Duplication Checks
            if admission_number and status != "REJECTED" and row_branch_id:
                if self.repository.check_admission_number_exists(self.tenant_id, row_branch_id, admission_number):
                    errors.append({"field": "Admission Number", "message": f"Admission number '{admission_number}' already exists in branch."})
                    status = "REJECTED"

            if not student_mobile:
                errors.append({"field": "Student Mobile", "message": "Missing optional field."})
                if status == "VALID":
                    status = "WARNING"

            normalized_data = {
                "student_name": student_name,
                "admission_number": admission_number,
                "date_of_birth": dob_val,
                "gender": gender or "UNKNOWN",
                "student_mobile": student_mobile if student_mobile else None,
                "guardian_name": guardian_name,
                "guardian_relationship": guardian_rel,
                "guardian_mobile": guardian_mobile,
                "year_level": year_level,
                "roll_number": roll_number if roll_number else None,
                "joining_date": joining_val,
                "academic_year_id": str(academic_year_id) if academic_year_id else None,
                "programme_id": str(programme_id) if programme_id else None,
                "batch_id": str(batch_id) if batch_id else None,
                "section_id": str(section_id) if section_id else None,
                "branch_id": str(row_branch_id) if row_branch_id else None,
            }

            if status == "VALID":
                summary["valid_rows"] += 1
            elif status == "WARNING":
                summary["warning_rows"] += 1
            else:
                summary["rejected_rows"] += 1

            results.append({
                "row_number": row_idx,
                "raw_data": {k: str(v) for k, v in raw_data.items()},
                "normalized_data": normalized_data,
                "validation_status": status,
                "errors": errors,
            })

        return results, summary
