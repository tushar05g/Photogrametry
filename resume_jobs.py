import os
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# We need to call celery tasks, so we import them.
# Ensure PYTHONPATH includes the root directory.
try:
    from worker.pipeline.tasks import initiate_pipeline
except ImportError:
    import sys
    sys.path.append(os.getcwd())
    from worker.pipeline.tasks import initiate_pipeline

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

def resume_all_pending():
    """Finds all PENDING jobs and triggers initiate_pipeline task for each."""
    with engine.connect() as conn:
        pending_jobs = conn.execute(text("SELECT job_id FROM jobs WHERE status = 'PENDING'")).fetchall()
        print(f"🚀 Found {len(pending_jobs)} pending jobs to resume...")
        for row in pending_jobs:
            jid = row[0]
            print(f"  -> Triggering job {jid}")
            # initiate_pipeline(job_id, image_urls=None)
            # Resuming without image_urls will use what's already in the DB/storage.
            initiate_pipeline.delay(jid)
        conn.commit()
    print("✅ All jobs resumed.")

if __name__ == "__main__":
    resume_all_pending()
