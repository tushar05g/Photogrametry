import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
job_id = "2d0d7c86-c3d4-4093-b6e4-fc31440e0631"

with engine.connect() as conn:
    print(f"=== STAGES FOR JOB {job_id} ===")
    res = conn.execute(text("SELECT stage_name, status, start_time, end_time, error_message FROM stages WHERE job_id = :job_id ORDER BY id"), {"job_id": job_id})
    for row in res:
        print(f"Stage: {row[0]} | Status: {row[1]} | Error: {row[4]}")
