import uuid
from sqlalchemy import text
from app.core.database.session import get_engine

def seed_database():
    """Seeds prerequisite campus branches, subjects, programmes, and students into PostgreSQL."""
    engine = get_engine()
    
    tenant_id = "e0bb112a-1da7-44e2-8988-a90dc7b5cca5"

    user_id = "00000000-0000-0000-0000-000000000002"

    with engine.begin() as conn:
        print("Seeding PostgreSQL Prerequisite Master Data...")

        # 1. Seed Tenant
        conn.execute(
            text("""
                INSERT INTO sms_tenants (id, tenant_code, legal_name, display_name, status, created_at, updated_at)
                VALUES (:id, 'SVIC', 'Sri Vignan Intermediate College', 'Sri Vignan College', 'ACTIVE', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"id": tenant_id}
        )

        # 2. Seed System User (for created_by FKs)
        conn.execute(
            text("""
                INSERT INTO sms_users (id, tenant_id, account_category, full_name, email, status, created_at, updated_at)
                VALUES (:id, :tenant_id, 'TENANT', 'Pramod Dean', 'dean@svic.edu', 'ACTIVE', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"id": user_id, "tenant_id": tenant_id}
        )

        # 3. Seed Campus Branches
        branch_hyd = "11111111-1111-1111-1111-111111111111"
        branch_vjy = "22222222-2222-2222-2222-222222222222"
        branch_vizag = "33333333-3333-3333-3333-333333333333"

        conn.execute(
            text("""
                INSERT INTO sms_branches (id, tenant_id, branch_code, display_name, status, created_at, updated_at)
                VALUES 
                    (:b1, :tenant_id, 'HYD-MAIN', 'Hyderabad Main Campus', 'DRAFT', NOW(), NOW()),
                    (:b2, :tenant_id, 'VJY-CITY', 'Vijayawada City Campus', 'DRAFT', NOW(), NOW()),
                    (:b3, :tenant_id, 'VIZAG-COAST', 'Visakhapatnam Campus', 'DRAFT', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"b1": branch_hyd, "b2": branch_vjy, "b3": branch_vizag, "tenant_id": tenant_id}
        )

        # 4. Seed Academic Year
        ay_id = "44444444-4444-4444-4444-444444444444"
        conn.execute(
            text("""
                INSERT INTO sms_academic_years (id, tenant_id, code, name, starts_on, ends_on, status, created_by, created_at, updated_at)
                VALUES (:id, :tenant_id, '2026-2027', 'Academic Year 2026–2027', '2026-06-01', '2027-04-30', 'ACTIVE', :created_by, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"id": ay_id, "tenant_id": tenant_id, "created_by": user_id}
        )

        # 5. Seed Course Programmes (Streams)
        prog_mpc = "55555555-5555-5555-5555-555555555555"
        prog_bipc = "66666666-6666-6666-6666-666666666666"
        conn.execute(
            text("""
                INSERT INTO sms_academic_programmes (id, tenant_id, programme_code, programme_name, status, created_by, created_at, updated_at)
                VALUES 
                    (:p1, :tenant_id, 'MPC', 'Maths, Physics, Chemistry', 'ACTIVE', :created_by, NOW(), NOW()),
                    (:p2, :tenant_id, 'BiPC', 'Biology, Physics, Chemistry', 'ACTIVE', :created_by, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"p1": prog_mpc, "p2": prog_bipc, "tenant_id": tenant_id, "created_by": user_id}
        )

        # 6. Seed Master Subjects
        sub_eng = "77777777-7777-7777-7777-777777777771"
        sub_sans = "77777777-7777-7777-7777-777777777772"
        sub_m1a = "77777777-7777-7777-7777-777777777773"
        sub_p1 = "77777777-7777-7777-7777-777777777774"
        sub_c1 = "77777777-7777-7777-7777-777777777775"

        conn.execute(
            text("""
                INSERT INTO sms_subjects (id, tenant_id, subject_code, subject_name, status, created_by, created_at, updated_at)
                VALUES 
                    (:s1, :tenant_id, 'ENG-101', 'English 1', 'ACTIVE', :created_by, NOW(), NOW()),
                    (:s2, :tenant_id, 'SAN-101', 'Sanskrit 1', 'ACTIVE', :created_by, NOW(), NOW()),
                    (:s3, :tenant_id, 'MATH-1A', 'Mathematics 1A', 'ACTIVE', :created_by, NOW(), NOW()),
                    (:s4, :tenant_id, 'PHY-101', 'Physics 1', 'ACTIVE', :created_by, NOW(), NOW()),
                    (:s5, :tenant_id, 'CHEM-101', 'Chemistry 1', 'ACTIVE', :created_by, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING;
            """),
            {"s1": sub_eng, "s2": sub_sans, "s3": sub_m1a, "s4": sub_p1, "s5": sub_c1, "tenant_id": tenant_id, "created_by": user_id}
        )

        print("PostgreSQL Prerequisite Master Data Seeded Successfully!")

if __name__ == "__main__":
    seed_database()
