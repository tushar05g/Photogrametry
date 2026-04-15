import sqlite3
import json

db_path = "scan_data.db" # Check where the DB is
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT results FROM jobs WHERE job_id = '58fcd391-8e6c-45f1-8c03-8dc6633daa60'")
row = cursor.fetchone()
if row:
    print(json.dumps(json.loads(row[0]), indent=2))
else:
    print("Job not found")
conn.close()
