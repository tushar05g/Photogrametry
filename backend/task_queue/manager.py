import redis
import os
from typing import Optional
from rq import Queue

# 🎓 Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_client: Optional[redis.Redis] = None
_queue: Optional[Queue] = None

def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client

def get_queue() -> Queue:
    """🎓 Singleton for the RQ Queue."""
    global _queue
    if _queue is None:
        # Note: We need a non-decoded client for RQ internally sometimes, 
        # but decode_responses=True is usually fine for simple strings.
        # However, RQ prefers a standard redis connection.
        conn = redis.from_url(REDIS_URL)
        _queue = Queue('morphic_cpu_queue', connection=conn)
    return _queue

def enqueue_job(job_id: str, image_urls: list, project_name: str) -> None:
    """
    🎓 ENQUEUE: Pushes a 3D generation task to the RQ queue.
    """
    from core.workers.cpu_worker import process_3d_model  # Updated import
    
    q = get_queue()
    q.enqueue(
        process_3d_model, 
        args=(job_id, image_urls, project_name),
        job_id=job_id # Use our DB job_id as the RQ job_id for easy lookup
    )
    print(f"✅ [Queue] Job {job_id} enqueued via RQ.")

def get_job_status(job_id: str) -> str:
    """🎓 Fetches the status of a job from RQ."""
    q = get_queue()
    job = q.fetch_job(job_id)
    if job:
        return job.get_status()
    return "unknown"
