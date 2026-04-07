import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ No DATABASE_URL found")
    exit(1)

engine = create_engine(DATABASE_URL)

def reset_job_stages(job_id: str):
    with engine.connect() as conn:
        print(f"🔄 Resetting stages for job {job_id}...")
        # Delete entries in stages table so they are not 'completed'
        conn.execute(text("DELETE FROM stages WHERE job_id = :job_id"), {"job_id": job_id})
        # Reset job status
        conn.execute(text("UPDATE jobs SET status = 'PENDING', current_stage = 'IDLE' WHERE job_id = :job_id"), {"job_id": job_id})
        conn.commit()
        print(f"✅ Job {job_id} reset to PENDING.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reset_job.py <job_id>")
        exit(1)
    reset_job_stages(sys.argv[1])
