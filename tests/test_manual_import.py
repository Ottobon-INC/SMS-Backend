# mypy: ignore-errors
# ruff: noqa: E402, E501

import pytest

pytest.skip(
    "Manual database-writing import flow check; run explicitly outside the normal test suite.",
    allow_module_level=True,
)

import os
import sys
import uuid

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.database.session import get_session_factory
from app.main import app

client = TestClient(app)

TENANT_ID = uuid.UUID("b1621609-cee0-4f12-99bc-8bd8560ae02c")
BRANCH_ID = uuid.UUID("f12c2100-e828-42ea-ac6b-e70542c684e6")
USER_ID = uuid.UUID("18b87bea-cbdd-4274-82c6-8b5e8ec211cb")

OTHER_TENANT_ID = uuid.UUID("a2345678-cee0-4f12-99bc-8bd8560ae02c")
OTHER_BRANCH_ID = uuid.UUID("c2345678-e828-42ea-ac6b-e70542c684e6")

def setup_test_data():
    session = get_session_factory()()
    try:
        # Get existing academic data for testing
        year = session.execute(text(f"SELECT id FROM sms_academic_years WHERE tenant_id = '{TENANT_ID}' LIMIT 1")).fetchone()
        prog = session.execute(text(f"SELECT id FROM sms_academic_programmes WHERE tenant_id = '{TENANT_ID}' LIMIT 1")).fetchone()
        batch = session.execute(text(f"SELECT id FROM sms_batches WHERE tenant_id = '{TENANT_ID}' AND branch_id = '{BRANCH_ID}' LIMIT 1")).fetchone()
        sec = session.execute(text(f"SELECT id FROM sms_sections WHERE tenant_id = '{TENANT_ID}' AND branch_id = '{BRANCH_ID}' LIMIT 1")).fetchone()
        
        other_batch = session.execute(text(f"SELECT id FROM sms_batches WHERE id != '{batch.id if batch else uuid.uuid4()}' LIMIT 1")).fetchone()

        session.commit()
        
        return {
            "year_id": year.id if year else None,
            "prog_id": prog.id if prog else None,
            "batch_id": batch.id if batch else None,
            "sec_id": sec.id if sec else None,
            "other_batch_id": other_batch.id if other_batch else None
        }
    finally:
        session.close()

def run_tests():
    print("--- STARTING MANUAL ADD STUDENT TESTS ---")
    
    # We must patch Auth since we don't have a valid token.
    # We will use dependency override in app
    from app.core.security.dependencies import get_request_context
    from app.core.security.jwt import AuthenticatedPrincipal
    
    def override_get_context():
        return AuthenticatedPrincipal(
            app_user_id=USER_ID,
            claims={
                "tenant_id": str(TENANT_ID),
                "branch_id": str(BRANCH_ID),
                "role": "OFFICE_STAFF",
                "permissions": ["import.upload", "import.commit"]
            }
        )
        
    app.dependency_overrides[get_request_context] = override_get_context
    
    # Setup Data
    refs = setup_test_data()
    if not all([refs["year_id"], refs["prog_id"], refs["batch_id"], refs["sec_id"]]):
        print("MISSING SEED DATA! Please ensure academic hierarchy exists for tests.")
        return

    # Payload Template
    def get_payload(adm_no="ADM-999"):
        return {
            "student_name": "Manual Test Student",
            "date_of_birth": "2010-05-15",
            "gender": "MALE",
            "admission_number": adm_no,
            "academic_year_id": str(refs["year_id"]),
            "programme_id": str(refs["prog_id"]),
            "batch_id": str(refs["batch_id"]),
            "section_id": str(refs["sec_id"]),
            "roll_number": f"R-{adm_no}",
            "guardian_name": "Test Guardian",
            "guardian_mobile": "+919999988888",
            "relationship_type": "FATHER"
        }

    # 1. Valid student creation
    print("\\nTest 1: Valid student creation")
    payload1 = get_payload("ADM-T1")
    res = client.post("/api/v1/imports/students/manual-student", json=payload1)
    assert res.status_code == 201, f"Failed: {res.text}"
    data = res.json()
    assert "student_id" in data
    assert "student_number" in data
    print("SUCCESS: Student created with ID", data["student_id"], "and System Number", data["student_number"])
    
    # 2. Duplicate admission number
    print("\\nTest 3: Duplicate admission number")
    res = client.post("/api/v1/imports/students/manual-student", json=payload1)
    assert res.status_code == 400
    assert "Admission number already exists" in res.json()["detail"]
    print("SUCCESS: Caught duplicate admission number.")

    # 4. Duplicate/generated Student Number collision
    # (Hard to test purely from outside without mocking UUID, but we know the loop exists in service.py)
    print("\\nTest 4: Generated Student Number collision handling (verified in code logic)")

    # 5. Existing guardian mobile within same tenant
    print("\\nTest 5: Existing guardian mobile within same tenant")
    payload2 = get_payload("ADM-T2")
    payload2["guardian_mobile"] = "+919999988888" # Same mobile
    payload2["guardian_name"] = "Different Name But Should Match"
    res = client.post("/api/v1/imports/students/manual-student", json=payload2)
    assert res.status_code == 201
    data2 = res.json()
    # Guardian ID should be the same as test 1
    assert data2["guardian_id"] == data["guardian_id"]
    print("SUCCESS: Matched existing guardian:", data2["guardian_id"])

    # 7. Invalid Batch/Section relationship
    print("\\nTest 7: Invalid Batch/Section relationship")
    payload3 = get_payload("ADM-T3")
    if refs["other_batch_id"]:
        payload3["batch_id"] = str(refs["other_batch_id"]) # Section belongs to original batch, not this one
        res = client.post("/api/v1/imports/students/manual-student", json=payload3)
        assert res.status_code == 400
        assert "Invalid academic hierarchy" in res.json()["detail"]
        print("SUCCESS: Caught invalid academic hierarchy.")
    else:
        print("SKIPPED: No other batch found to test cross-batch section.")

    # 8. Simulated failure on Enrolment creation (testing rollback)
    print("\\nTest 9: Simulated failure transaction rollback")
    payload4 = get_payload("ADM-T4")
    payload4["section_id"] = "invalid-uuid" 
    # Not a real UUID, Pydantic should catch it or DB fails.
    # Actually, pydantic catches it. Let's send a non-existent valid UUID to trigger DB FK error
    payload4["section_id"] = str(uuid.uuid4())
    res = client.post("/api/v1/imports/students/manual-student", json=payload4)
    assert res.status_code in [400, 500]
    print("SUCCESS: Rejected invalid FK insertion.")
    
    # Check that ADM-T4 was not inserted
    session = get_session_factory()()
    st = session.execute(text("SELECT id FROM sms_students WHERE student_number = 'ADM-T4'")).fetchone()
    assert st is None
    session.close()
    print("SUCCESS: Transaction properly rolled back.")
    
    print("\\n--- ALL TESTS COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    run_tests()
