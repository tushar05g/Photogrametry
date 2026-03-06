"""
🎓 TEACHER'S NOTE — backend/queue/manager.py
=============================================
PURPOSE: This is our "Job Dispatcher". It puts jobs into a Redis queue
and distributes them to available GPU workers.

WHY REDIS?
-----------
A "Job Queue" is like a to-do list that never gets lost, even if the server restarts.
Without Redis, if your FastAPI server restarts while a job is "pending", you lose it.
Redis stores the queue in memory (fast) AND on disk (persistent), so jobs survive.

HOW IT WORKS (Data Flow):
1. User uploads images → FastAPI pushes a job ID to Redis (like putting a ticket in a box).
2. A GPU Worker makes a GET request to /workers/next-job.
3. FastAPI pops the ticket from Redis and sends it to the available worker.
4. The worker does the heavy GPU work and reports back when done.

REDIS COMMANDS USED:
- RPUSH: Add item to the RIGHT end of the list (enqueue).
- BLPOP: Remove item from the LEFT end, BLOCKING for up to N seconds if empty (dequeue).
         "Blocking" means the server waits intelligently instead of wasting CPU in a loop.
"""

import redis
import json
import os
from typing import Optional

# 🎓 Redis connection — "scanner_redis" is the Docker service name.
# Inside the Docker network, services can talk to each other by service name.
REDIS_URL = os.getenv("REDIS_URL", "redis://scanner_redis:6379/0")
_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    🎓 Singleton pattern: Creates the Redis client ONCE and reuses it.
    Creating a new connection for every request is wasteful (imagine opening
    a new internet connection every time you load a webpage).
    """
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client


JOB_QUEUE_KEY = "morphic:job_queue"


def enqueue_job(job_id: str) -> None:
    """
    🎓 ENQUEUE: Pushes a job ID to the rightmost end of the Redis list.

    Think of it like a real-world print queue:
    - RPUSH adds the job to the END of the line.
    - BLPOP takes the job from the FRONT of the line (FIFO order = fair queue).
    
    We only store the job ID in Redis. All actual job data lives in PostgreSQL.
    Redis is just the "signal" — the worker uses the ID to fetch real data from the DB.
    """
    r = get_redis()
    r.rpush(JOB_QUEUE_KEY, job_id)
    print(f"✅ [Queue] Job {job_id} added to the queue.")


def dequeue_job(timeout: int = 0) -> Optional[str]:
    """
    🎓 DEQUEUE: Pops the next available job from the FRONT of the queue.
    timeout=0 means it returns immediately (None if empty).
    """
    r = get_redis()
    result = r.lpop(JOB_QUEUE_KEY)
    return result  # Returns the job_id string, or None if empty


def queue_length() -> int:
    """Returns how many jobs are currently waiting in the queue."""
    r = get_redis()
    return r.llen(JOB_QUEUE_KEY)
