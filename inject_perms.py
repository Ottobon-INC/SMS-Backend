import psycopg2
import uuid

conn = psycopg2.connect('postgresql://postgres.nplkzirfrpgthatjkehj:Ottobon%402525@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres')
cur = conn.cursor()

# 1. Insert permissions
exam_manage_id = str(uuid.uuid4())
exam_publish_id = str(uuid.uuid4())

cur.execute("INSERT INTO sms_permissions (id, permission_key, module_code, description) VALUES (%s, 'exam.manage', 'examinations', 'Manage assessments (Create, edit setup)') ON CONFLICT (permission_key) DO NOTHING", (exam_manage_id,))
cur.execute("INSERT INTO sms_permissions (id, permission_key, module_code, description) VALUES (%s, 'exam.publish', 'examinations', 'Approve and publish results') ON CONFLICT (permission_key) DO NOTHING", (exam_publish_id,))

# Get exact IDs in case they already existed
cur.execute("SELECT id FROM sms_permissions WHERE permission_key = 'exam.manage'")
exam_manage_id = cur.fetchone()[0]
cur.execute("SELECT id FROM sms_permissions WHERE permission_key = 'exam.publish'")
exam_publish_id = cur.fetchone()[0]

# 2. Get target role IDs
cur.execute("SELECT id, role_code FROM sms_roles WHERE role_code IN ('INSTITUTION_ADMIN', 'BRANCH_ADMIN', 'SUPER_ADMIN', 'PRINCIPAL')")
roles = cur.fetchall()

# 3. Map permissions to roles
for role_id, role_code in roles:
    cur.execute("INSERT INTO sms_role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (role_id, exam_manage_id))
    cur.execute("INSERT INTO sms_role_permissions (role_id, permission_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (role_id, exam_publish_id))

conn.commit()
print('Permissions injected successfully!')
