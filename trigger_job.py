import os
import sys
from backend.core.celery_app import celery_app
from worker.pipeline.tasks import initiate_pipeline

def trigger(job_id: str):
    print(f"Triggering job {job_id}...")
    initiate_pipeline.apply_async(
        kwargs={"job_id": job_id, "enable_splat": True},
        task_id=f"manual-{job_id}"
    )
    print("Task sent to Redis.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trigger_job.py <job_id>")
        sys.exit(1)
    trigger(sys.argv[1])
