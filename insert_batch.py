
import psycopg
import uuid
conn = psycopg.connect('postgresql://postgres.nplkzirfrpgthatjkehj:Ottobon%402525@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres')
cur = conn.cursor()
cur.execute('SELECT id FROM sms_tenants LIMIT 1')
tenant_id = cur.fetchone()[0]
cur.execute('SELECT id FROM sms_users WHERE tenant_id = %s LIMIT 1', (tenant_id,))
user_id = cur.fetchone()[0]
cur.execute('''
INSERT INTO sms_batches (id, tenant_id, branch_id, academic_year_id, programme_id, batch_code, batch_name, year_level, status, created_by)
VALUES (%s, %s, '8854ab2a-44cf-4770-bb51-5f78e0876e9d', '30000000-0000-0000-0000-000000000001', '946da781-d270-4a5a-b9d5-3a245952bbf1', 'MPC-TEST-2', 'MPC Test Batch 2', 'FIRST_YEAR', 'ACTIVE', %s)
''', (str(uuid.uuid4()), tenant_id, user_id))
conn.commit()
print('Inserted MPC Test Batch 2!')
conn.close()

