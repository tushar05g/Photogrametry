import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def reset_all_failed():
    with engine.connect() as conn:
        failed_jobs = conn.execute(text("SELECT job_id FROM jobs WHERE status = 'FAILED'")).fetchall()
        for row in failed_jobs:
            jid = row[0]
            print(f"🔄 Resetting job {jid}...")
            # We don't delete stages entirely, we set them to FAILED so initiate_pipeline picks them up
            # Wait, initiate_pipeline uses is_stage_completed (which checks for COMPLETED)
            # So just setting job to PENDING and current_stage to IDLE should be enough to RESTART from the first non-completed stage.
            # But the user wants to FIX SFM, so we should delete stages from SFM onwards.
            conn.execute(text("DELETE FROM stages WHERE job_id = :job_id"), {"job_id": jid})
            conn.execute(text("UPDATE jobs SET status = 'PENDING', current_stage = 'IDLE' WHERE job_id = :job_id"), {"job_id": jid})
        conn.commit()
        print(f"✅ Reset {len(failed_jobs)} failed jobs.")

if __name__ == "__main__":
    reset_all_failed()
