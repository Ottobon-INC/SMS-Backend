import psycopg2

try:
    conn = psycopg2.connect("dbname=student_operations user=postgres password=postgres host=localhost")
    cur = conn.cursor()
    cur.execute("SELECT id FROM sms_exams WHERE status='PUBLISHED' LIMIT 1")
    exam = cur.fetchone()
    if not exam:
        print("No published exam found")
    else:
        exam_id = exam[0]
        print(f"Found exam_id: {exam_id}")
        cur.execute("SELECT subject_marks FROM sms_student_exam_records WHERE exam_id = %s LIMIT 1", (exam_id,))
        marks = cur.fetchone()
        print(f"Marks: {marks}")
        
        cur.execute("SELECT COUNT(*) FROM sms_notification_logs")
        logs = cur.fetchone()
        print(f"Total Logs: {logs[0]}")
        
except Exception as e:
    print(f"Error: {e}")
