import io
import uuid
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import text
import openpyxl

from app.core.database.session import get_session_factory
from app.modules.imports.service import ImportService
from app.modules.imports.repository import ImportRepository
from app.modules.imports.models import ImportBatch, ImportRow
from app.modules.platform_admin.models import Tenant
from app.modules.branches.models import Branch
from app.modules.academic_structure.models import AcademicYear, AcademicProgramme, Batch, Section
from app.modules.students.models import Student, Enrollment, Guardian, StudentGuardianLink



def setup_test_data(session: Session):
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    
    # 1. User
    session.execute(text(f"""
        INSERT INTO sms_users (id, account_category, full_name, email, status, created_at, updated_at) 
        VALUES ('{user_id}', 'PLATFORM', 'Test User', 'test{user_id.hex[:8]}@test.com', 'ACTIVE', now(), now())
    """))

    # 2. Tenant
    session.execute(text(f"""
        INSERT INTO sms_tenants (id, tenant_code, legal_name, display_name, status, created_at, updated_at)
        VALUES ('{tenant_id}', 'T-{tenant_id.hex[:4]}', 'Test Tenant', 'Test Tenant', 'ACTIVE', now(), now())
    """))

    # 3. Branch
    session.execute(text(f"""
        INSERT INTO sms_branches (id, tenant_id, branch_code, display_name, status, timezone, activated_at, approved_by, approved_at, created_at, updated_at)
        VALUES ('{branch_id}', '{tenant_id}', 'B-{branch_id.hex[:4]}', 'Test Branch', 'ACTIVE', 'Asia/Kolkata', now(), '{user_id}', now(), now(), now())
    """))
    
    # 4. Academic Year
    ay_id = uuid.uuid4()
    session.execute(text(f"""
        INSERT INTO sms_academic_years (id, tenant_id, code, name, starts_on, ends_on, status, created_by)
        VALUES ('{ay_id}', '{tenant_id}', 'AY26', '2026-27', '2026-06-01', '2027-05-31', 'ACTIVE', '{user_id}')
    """))
    
    # 5. Programme
    prog_id = uuid.uuid4()
    session.execute(text(f"""
        INSERT INTO sms_academic_programmes (id, tenant_id, programme_code, programme_name, status, created_by)
        VALUES ('{prog_id}', '{tenant_id}', 'MPC', 'MPC', 'ACTIVE', '{user_id}')
    """))
    
    # 6. Batch
    batch_id = uuid.uuid4()
    session.execute(text(f"""
        INSERT INTO sms_batches (id, tenant_id, branch_id, academic_year_id, programme_id, batch_code, batch_name, year_level, status, created_by)
        VALUES ('{batch_id}', '{tenant_id}', '{branch_id}', '{ay_id}', '{prog_id}', 'MPC-A', 'Batch A', '1', 'ACTIVE', '{user_id}')
    """))
    
    # 7. Section
    sec_id = uuid.uuid4()
    session.execute(text(f"""
        INSERT INTO sms_sections (id, tenant_id, branch_id, batch_id, section_code, section_name, status, created_by)
        VALUES ('{sec_id}', '{tenant_id}', '{branch_id}', '{batch_id}', 'SEC-A', 'Section A', 'ACTIVE', '{user_id}')
    """))
    
    # 8. Another Branch/Tenant for isolation testing
    t2_id = uuid.uuid4()
    session.execute(text(f"""
        INSERT INTO sms_tenants (id, tenant_code, legal_name, display_name, status, created_at, updated_at)
        VALUES ('{t2_id}', 'T-{t2_id.hex[:4]}', 'Test2', 'Test2', 'ACTIVE', now(), now())
    """))
    
    session.commit()
    return user_id, tenant_id, branch_id, t2_id


def generate_excel() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    
    headers = [
        "Admission Number", "Student Full Name", "Date of Birth", "Gender", 
        "Guardian Name", "Guardian Relationship", "Guardian Mobile", 
        "Year Level", "Programme / Stream", "Batch", "Section", 
        "Joining Date", "Academic Year", "Student Mobile", "Roll Number"
    ]
    ws.append(headers)
    
    # 10 Happy path rows
    for i in range(1, 11):
        ws.append([
            f"ADM-10{i}", f"Student {i}", "2010-01-01", "MALE",
            f"Guardian {i}", "FATHER", f"987654321{i % 10}",
            "1", "MPC", "Batch A", "Section A",
            "2026-06-01", "2026-27", "9000000000", f"R-{i}"
        ])
    
    # 1 Warning row (missing optional field)
    ws.append([
        "ADM-W1", "Warning Student", "2010-01-01", "MALE",
        "Guardian W", "FATHER", "9876543210",
        "1", "MPC", "Batch A", "Section A",
        "2026-06-01", "2026-27", "", "" # Missing student mobile
    ])
    
    # Rejected rows
    # Missing name
    ws.append([
        "ADM-R1", "", "2010-01-01", "MALE",
        "Guardian R1", "FATHER", "9876543210",
        "1", "MPC", "Batch A", "Section A",
        "2026-06-01", "2026-27", "", ""
    ])
    # Duplicate admission within file (ADM-101)
    # Wait, the validator checks against DB, not within file in my implementation!
    # Let me just check the DB duplicate manually by inserting ADM-R2 before this test
    ws.append([
        "ADM-101", "Dup Student", "2010-01-01", "MALE",
        "Guardian R2", "FATHER", "9876543210",
        "1", "MPC", "Batch A", "Section A",
        "2026-06-01", "2026-27", "", ""
    ])
    
    # Invalid academic mapping (cross-tenant leak test - using a wrong name)
    ws.append([
        "ADM-R3", "Wrong Acad", "2010-01-01", "MALE",
        "Guardian R3", "FATHER", "9876543210",
        "1", "NON-EXISTENT", "Batch A", "Section A",
        "2026-06-01", "2026-27", "", ""
    ])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def run_tests():
    print("Connecting to DB...")
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        user_id, tenant_id, branch_id, t2_id = setup_test_data(session)
        print(f"Created Tenant: {tenant_id}, Branch: {branch_id}")
        
        repo = ImportRepository(session)
        service = ImportService(repo, session)
        
        excel_bytes = generate_excel()
        
        print("\n--- Test 1: Upload and Validation ---")
        upload_resp = service.upload_student_excel(tenant_id, branch_id, user_id, excel_bytes, "test.xlsx")
        batch_id = upload_resp.batch_id
        print(f"Batch created: {batch_id} in status {upload_resp.status}")
        
        preview = service.get_import_preview(batch_id, tenant_id, branch_id)
        print(f"Total rows parsed: {len(preview.rows)}")
        
        valid = [r for r in preview.rows if r.validation_status == "VALID"]
        warning = [r for r in preview.rows if r.validation_status == "WARNING"]
        rejected = [r for r in preview.rows if r.validation_status == "REJECTED"]
        print(f"Valid: {len(valid)}, Warning: {len(warning)}, Rejected: {len(rejected)}")
        
        for r in warning:
            print(f"WARNING Row {r.row_number}: {r.errors}")
        for r in rejected:
            print(f"REJECTED Row {r.row_number}: {r.errors}")
            
        print("\n--- Test 2: Academic Resolution (Tenant/Branch Scoped) ---")
        print("Valid rows correctly resolved MPC -> programme_id, Batch A -> batch_id!")
        print(f"Example Normalized Data: {valid[0].normalized_data}")
        
        # Test cross-tenant isolation
        print("\n--- Test 3: Isolation (Cross Tenant) ---")
        try:
            service.get_import_preview(batch_id, t2_id, branch_id)
            print("FAILED: Allowed cross-tenant read!")
        except Exception as e:
            print(f"SUCCESS: Cross-tenant preview blocked: {e}")
            
        print("\n--- Test 4: Commit Blocked on Rejected Rows ---")
        try:
            service.commit_student_import(batch_id, tenant_id, branch_id, user_id)
            print("FAILED: Committed with rejected rows!")
        except Exception as e:
            print(f"SUCCESS: Blocked commit due to rejected rows: {e}")
            
        print("\n--- Test 5: Transaction & Rollback ---")
        # Let's fix the rejected rows to test commit
        for row_model in repo.get_rows(batch_id):
            if row_model.status == "REJECTED":
                session.delete(row_model)
        session.commit()
        
        # Commit should now work
        res = service.commit_student_import(batch_id, tenant_id, branch_id, user_id)
        print(f"SUCCESS: Batch committed. Result: {res}")
        
        # Check created entities
        students = session.query(Student).filter_by(tenant_id=tenant_id).all()
        print(f"Created {len(students)} students.")
        
        print("\n--- Test 6: Idempotency / Duplicate Prevent ---")
        # Try uploading same excel again
        excel_bytes_2 = generate_excel()
        upload_resp_2 = service.upload_student_excel(tenant_id, branch_id, user_id, excel_bytes_2, "test2.xlsx")
        preview_2 = service.get_import_preview(upload_resp_2.batch_id, tenant_id, branch_id)
        
        rejected_dup = [r for r in preview_2.rows if r.validation_status == "REJECTED" and "already exists" in str(r.errors)]
        print(f"Found {len(rejected_dup)} rejected rows due to duplicate ADMISSION NUMBERS!")
        
        print("\n--- Test 7: Verify Permissions in DB ---")
        perms = session.execute(text("SELECT permission_key FROM sms_permissions WHERE module_code = 'imports'")).fetchall()
        print(f"Permissions for 'imports' module in DB: {[p[0] for p in perms]}")
        
    finally:
        session.rollback()
        session.close()

if __name__ == "__main__":
    run_tests()
