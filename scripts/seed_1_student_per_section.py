"""Script to seed 1 unique student + primary guardian per class section across all campus branches.

Follows full 4-table relational database integrity:
1. sms_students
2. sms_guardians
3. sms_student_guardian_links
4. sms_enrollments
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import uuid
from datetime import datetime
from sqlalchemy import text
from app.core.database.session import get_engine

DEFAULT_TENANT_ID = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"
DEFAULT_USER_ID = "842021d3-9826-4c4f-ad83-504be45d4520"
DEFAULT_ACADEMIC_YEAR_ID = "44444444-4444-4444-4444-444444444444"

# 20 Unique Student & Guardian Profiles
STUDENT_ROSTER = [
    {"legal_name": "Karthik Varma", "gender": "MALE", "guardian_name": "Venkat Varma", "mobile": "+91 98765 10001", "email": "karthik.varma@gmail.com"},
    {"legal_name": "Ananya Reddy", "gender": "FEMALE", "guardian_name": "Narasimha Reddy", "mobile": "+91 98765 10002", "email": "ananya.reddy@gmail.com"},
    {"legal_name": "Sai Teja", "gender": "MALE", "guardian_name": "Srinivas Teja", "mobile": "+91 98765 10003", "email": "sai.teja@gmail.com"},
    {"legal_name": "Divya Sri", "gender": "FEMALE", "guardian_name": "Subba Rao", "mobile": "+91 98765 10004", "email": "divya.sri@gmail.com"},
    {"legal_name": "Tarun Rao", "gender": "MALE", "guardian_name": "Koteswara Rao", "mobile": "+91 98765 10005", "email": "tarun.rao@gmail.com"},
    {"legal_name": "Pooja Sharma", "gender": "FEMALE", "guardian_name": "Ramesh Sharma", "mobile": "+91 98765 10006", "email": "pooja.sharma@gmail.com"},
    {"legal_name": "Rahul Chowdary", "gender": "MALE", "guardian_name": "Satyanarayana Chowdary", "mobile": "+91 98765 10007", "email": "rahul.chowdary@gmail.com"},
    {"legal_name": "Manish Gupta", "gender": "MALE", "guardian_name": "Suresh Gupta", "mobile": "+91 98765 10008", "email": "manish.gupta@gmail.com"},
    {"legal_name": "Sravani Raju", "gender": "FEMALE", "guardian_name": "Ramakrishna Raju", "mobile": "+91 98765 10009", "email": "sravani.raju@gmail.com"},
    {"legal_name": "Vikram Aditya", "gender": "MALE", "guardian_name": "Aditya Prasad", "mobile": "+91 98765 20001", "email": "vikram.aditya@gmail.com"},
    {"legal_name": "Harini Naidu", "gender": "FEMALE", "guardian_name": "Jagadeesh Naidu", "mobile": "+91 98765 20002", "email": "harini.naidu@gmail.com"},
    {"legal_name": "Akash Mishra", "gender": "MALE", "guardian_name": "Sunil Mishra", "mobile": "+91 98765 20003", "email": "akash.mishra@gmail.com"},
    {"legal_name": "Meghana Varma", "gender": "FEMALE", "guardian_name": "Bhaskar Varma", "mobile": "+91 98765 20004", "email": "meghana.varma@gmail.com"},
    {"legal_name": "Pranav Kumar", "gender": "MALE", "guardian_name": "Vijay Kumar", "mobile": "+91 98765 30001", "email": "pranav.kumar@gmail.com"},
    {"legal_name": "Kavya Sri", "gender": "FEMALE", "guardian_name": "Prabhakar Rao", "mobile": "+91 98765 30002", "email": "kavya.sri@gmail.com"},
    {"legal_name": "Nikhil Varma", "gender": "MALE", "guardian_name": "Mohan Varma", "mobile": "+91 98765 30003", "email": "nikhil.varma@gmail.com"},
    {"legal_name": "Rohan Sharma", "gender": "MALE", "guardian_name": "Dinesh Sharma", "mobile": "+91 98765 40001", "email": "rohan.sharma@gmail.com"},
    {"legal_name": "Sneha Latha", "gender": "FEMALE", "guardian_name": "Appa Rao", "mobile": "+91 98765 40002", "email": "sneha.latha@gmail.com"},
    {"legal_name": "Yashwanth Reddy", "gender": "MALE", "guardian_name": "Malla Reddy", "mobile": "+91 98765 40003", "email": "yashwanth.reddy@gmail.com"},
    {"legal_name": "Bhavana K", "gender": "FEMALE", "guardian_name": "Kishore K", "mobile": "+91 98765 40004", "email": "bhavana.k@gmail.com"},
]

def run_seeding():
    engine = get_engine()
    print("🚀 Starting Relational Student & Guardian Seeding (1 per section)...")

    with engine.begin() as conn:
        # 1. Fetch default Academic Year ID
        ay_row = conn.execute(
            text("SELECT id FROM sms_academic_years WHERE tenant_id = :t AND status = 'ACTIVE' ORDER BY is_default DESC LIMIT 1"),
            {"t": DEFAULT_TENANT_ID}
        ).fetchone()
        ay_id = str(ay_row.id) if ay_row else DEFAULT_ACADEMIC_YEAR_ID

        # 2. Ensure default batches & sections exist for 'bhanu' campus branch
        bhanu_branch = conn.execute(
            text("SELECT id FROM sms_branches WHERE tenant_id = :t AND (display_name ILIKE '%bhanu%' OR branch_code ILIKE '%bhanu%') LIMIT 1"),
            {"t": DEFAULT_TENANT_ID}
        ).fetchone()

        if bhanu_branch:
            b_id = str(bhanu_branch.id)
            default_bhanu_progs = [
                ("MPC", "MPC-1A", "First Year"),
                ("BiPC", "BiPC-1A", "First Year"),
                ("CEC", "CEC-1A", "First Year"),
                ("MEC", "MEC-1A", "First Year"),
            ]
            for p_code, sec_name, yr_level in default_bhanu_progs:
                prog_row = conn.execute(
                    text("SELECT id FROM sms_academic_programmes WHERE tenant_id = :t AND (programme_code = :code OR stream_code = :code) LIMIT 1"),
                    {"t": DEFAULT_TENANT_ID, "code": p_code}
                ).fetchone()
                
                if prog_row:
                    prog_id = str(prog_row.id)
                    batch_id = str(uuid.uuid4())
                    batch_code = f"BATCH-{p_code}-BHANU"
                    
                    # Create Batch
                    conn.execute(
                        text("""
                            INSERT INTO sms_batches (
                                id, tenant_id, branch_id, academic_year_id, programme_id,
                                batch_code, batch_name, year_level, status, created_by, created_at, updated_at
                            )
                            VALUES (
                                :id, :tenant_id, :branch_id, :ay_id, :prog_id,
                                :code, :name, :yr_level, 'ACTIVE', :user_id, NOW(), NOW()
                            )
                            ON CONFLICT DO NOTHING;
                        """),
                        {
                            "id": batch_id,
                            "tenant_id": DEFAULT_TENANT_ID,
                            "branch_id": b_id,
                            "ay_id": ay_id,
                            "prog_id": prog_id,
                            "code": batch_code,
                            "name": f"{p_code} Batch 1",
                            "yr_level": yr_level,
                            "user_id": DEFAULT_USER_ID,
                        }
                    )
                    
                    # Create Section
                    sec_code = f"{sec_name}-BHANU"
                    conn.execute(
                        text("""
                            INSERT INTO sms_sections (id, tenant_id, branch_id, batch_id, section_code, section_name, status, created_by, created_at, updated_at)
                            VALUES (:id, :tenant_id, :branch_id, :batch_id, :sec_code, :sec_name, 'ACTIVE', :created_by, NOW(), NOW())
                            ON CONFLICT DO NOTHING;
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "tenant_id": DEFAULT_TENANT_ID,
                            "branch_id": b_id,
                            "batch_id": batch_id,
                            "sec_code": sec_code,
                            "sec_name": sec_name,
                            "created_by": DEFAULT_USER_ID,
                        }
                    )

        # 3. Query all sections across all campus branches with batch & programme IDs
        all_sections = conn.execute(
            text("""
                SELECT
                    s.id AS section_id,
                    s.branch_id,
                    s.batch_id,
                    bt.programme_id,
                    s.section_name,
                    br.display_name AS branch_name
                FROM sms_sections s
                JOIN sms_batches bt ON bt.id = s.batch_id
                JOIN sms_branches br ON br.id = s.branch_id
                WHERE s.tenant_id = :t AND s.status = 'ACTIVE' AND br.status != 'INACTIVE'
                ORDER BY br.display_name, s.section_code
            """),
            {"t": DEFAULT_TENANT_ID}
        ).fetchall()

        print(f"📌 Found {len(all_sections)} active class sections across all campus branches.")

        roster_idx = 0
        total_created = 0

        for sec in all_sections:
            sec_id = str(sec.section_id)
            branch_id = str(sec.branch_id)
            batch_id = str(sec.batch_id)
            programme_id = str(sec.programme_id)

            # Check existing active enrollment for this section
            existing = conn.execute(
                text("SELECT count(*) FROM sms_enrollments WHERE tenant_id = :t AND section_id = :sec_id AND status = 'ACTIVE'"),
                {"t": DEFAULT_TENANT_ID, "sec_id": sec_id}
            ).scalar()

            if existing > 0:
                print(f"  ℹ️ Section {sec.branch_name} -> {sec.section_name} already has {existing} student(s). Skipping.")
                continue

            # Pick next student profile from roster
            profile = STUDENT_ROSTER[roster_idx % len(STUDENT_ROSTER)]
            roster_idx += 1

            student_id = str(uuid.uuid4())
            guardian_id = str(uuid.uuid4())
            link_id = str(uuid.uuid4())
            enrollment_id = str(uuid.uuid4())
            adm_num = f"ADM-2026-{(100 + roster_idx):03d}"

            # Step A: Insert Student Profile into sms_students
            conn.execute(
                text("""
                    INSERT INTO sms_students (
                        id, tenant_id, student_number, legal_name, display_name,
                        date_of_birth, gender, current_status, source_type, created_by, created_at, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, :adm_num, :name, :name,
                        CAST('2008-05-15' AS date), :gender, 'ACTIVE', 'MANUAL', :user_id, NOW(), NOW()
                    );
                """),
                {
                    "id": student_id,
                    "tenant_id": DEFAULT_TENANT_ID,
                    "adm_num": adm_num,
                    "name": profile["legal_name"],
                    "gender": profile["gender"],
                    "user_id": DEFAULT_USER_ID,
                }
            )

            # Step B: Insert Guardian Profile into sms_guardians
            conn.execute(
                text("""
                    INSERT INTO sms_guardians (
                        id, tenant_id, full_name, mobile, email,
                        verification_status, verified_at, status, created_by, created_at, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, :gname, :mobile, :email,
                        'VERIFIED', NOW(), 'ACTIVE', :user_id, NOW(), NOW()
                    );
                """),
                {
                    "id": guardian_id,
                    "tenant_id": DEFAULT_TENANT_ID,
                    "gname": profile["guardian_name"],
                    "mobile": profile["mobile"],
                    "email": profile["email"],
                    "user_id": DEFAULT_USER_ID,
                }
            )

            # Step C: Link Student & Primary Guardian in sms_student_guardian_links
            conn.execute(
                text("""
                    INSERT INTO sms_student_guardian_links (
                        id, tenant_id, student_id, guardian_id, relationship_type,
                        is_primary, portal_access_enabled, notification_enabled, verification_status, verified_at,
                        status, created_by, created_at, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, :student_id, :guardian_id, 'FATHER',
                        true, true, true, 'VERIFIED', NOW(),
                        'ACTIVE', :user_id, NOW(), NOW()
                    );
                """),
                {
                    "id": link_id,
                    "tenant_id": DEFAULT_TENANT_ID,
                    "student_id": student_id,
                    "guardian_id": guardian_id,
                    "user_id": DEFAULT_USER_ID,
                }
            )

            # Step D: Create Section Enrollment in sms_enrollments
            conn.execute(
                text("""
                    INSERT INTO sms_enrollments (
                        id, tenant_id, student_id, branch_id, academic_year_id,
                        programme_id, batch_id, section_id, admission_number, year_level,
                        status, joining_date, is_current, source_type, created_by, created_at, updated_at
                    )
                    VALUES (
                        :id, :tenant_id, :student_id, :branch_id, :ay_id,
                        :programme_id, :batch_id, :section_id, :adm_num, 'First Year',
                        'ACTIVE', CAST('2026-06-01' AS date), true, 'MANUAL', :user_id, NOW(), NOW()
                    );
                """),
                {
                    "id": enrollment_id,
                    "tenant_id": DEFAULT_TENANT_ID,
                    "student_id": student_id,
                    "branch_id": branch_id,
                    "ay_id": ay_id,
                    "programme_id": programme_id,
                    "batch_id": batch_id,
                    "section_id": sec_id,
                    "adm_num": adm_num,
                    "user_id": DEFAULT_USER_ID,
                }
            )

            total_created += 1
            print(f"  ✅ Enrolled {profile['legal_name']} ({adm_num}) -> {sec.branch_name} [{sec.section_name}] | Guardian: {profile['guardian_name']} ({profile['mobile']})")

    print(f"\n🎉 SUCCESS: Created {total_created} student & guardian pairs across all campus branch sections!")

if __name__ == "__main__":
    run_seeding()
