"""
🎓 TEACHER'S NOTE — backend/api/workers.py
============================================
PURPOSE: This is the "Worker Registry" — the switchboard that keeps track of all
available GPU workers (Kaggle notebooks with ngrok tunnels).

WHY A REGISTRY?
---------------
In a distributed system, workers are ephemeral (they can appear and disappear).
A Kaggle notebook might be restarted, run out of RAM, or lose its ngrok tunnel.
The registry lets us know WHICH workers are online and WHERE to send new jobs.

WORKER LIFECYCLE:
1. Worker starts on Kaggle (or any GPU machine).
2. Worker REGISTERS itself by calling: POST /workers/register { "url": "https://xyz.ngrok.io" }
3. Our DB stores the worker with status="idle".
4. When a new job comes in, our backend picks an idle worker and sends it the job via HTTP.
5. The worker sets its own status to "busy" while processing.
6. When done, the worker REPORTS BACK by calling: PATCH /scans/{job_id} { "status": "completed", "model_url": "..." }
7. Worker resets itself to "idle" and waits for the next job.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
import httpx

from backend.core.db import SessionLocal
from backend.models.models import ScanJob, JobStatus
from backend.queue.manager import dequeue_job, queue_length

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- SCHEMAS ---

class WorkerRegistration(BaseModel):
    """
    🎓 The data a worker sends when it comes online.
    - worker_id: A unique name the worker gives itself (e.g., "kaggle-gpu-1").
    - url: The public ngrok URL where the worker's own API is listening.
    """
    worker_id: str
    url: str  # e.g., "https://abc-xyz.ngrok-free.app"


class WorkerInfo(BaseModel):
    worker_id: str
    url: str
    status: str  # "idle" | "busy"
    last_seen: str


# --- IN-MEMORY REGISTRY ---
# 🎓 For simplicity, we store workers in memory. In production, this would be in Redis
# so the registry persists across backend restarts.
_WORKER_REGISTRY: dict[str, dict] = {}


# --- ENDPOINTS ---

@router.post("/register")
def register_worker(payload: WorkerRegistration):
    """
    🎓 Called by a GPU worker when it first starts up.
    The worker says: "I'm alive! Here's my URL."
    We store this so we can send jobs to that worker later.
    """
    _WORKER_REGISTRY[payload.worker_id] = {
        "worker_id": payload.worker_id,
        "url": payload.url,
        "status": "idle",
        "last_seen": datetime.now(timezone.utc).isoformat()
    }
    print(f"🛰️ [Registry] Worker '{payload.worker_id}' registered at {payload.url}")
    return {"message": f"Worker '{payload.worker_id}' registered successfully."}


@router.get("/list")
def list_workers():
    """Returns all currently registered workers and their status."""
    return {"workers": list(_WORKER_REGISTRY.values())}


@router.get("/next-job")
def get_next_job_for_worker(worker_id: str, db: Session = Depends(get_db)):
    """
    🎓 Called by a GPU worker to POLL for new work.
    
    This is the "Pull Model": workers ASK for jobs rather than the backend pushing.
    This is more resilient because:
    - The backend doesn't need to know worker URLs upfront.
    - Workers can join/leave at any time.
    - No job is lost if a worker crashes because the ID stays in the DB as "pending".
    """
    if worker_id not in _WORKER_REGISTRY:
        raise HTTPException(status_code=403, detail="Worker not registered. Call /workers/register first.")

    job_id = dequeue_job()
    if not job_id:
        return {"job_id": None, "message": "No jobs in queue"}

    # Verify job still exists and is still pending
    job = db.query(ScanJob).filter(
        ScanJob.id == job_id,
        ScanJob.status == JobStatus.pending
    ).first()

    if not job:
        return {"job_id": None, "message": "Job was cancelled or already taken"}

    # Mark worker as busy
    _WORKER_REGISTRY[worker_id]["status"] = "busy"

    return {
        "job_id": str(job.id),
        "images": [img.file_path for img in job.images],
        "project_name": job.project_name
    }


@router.post("/{worker_id}/idle")
def mark_worker_idle(worker_id: str):
    """Called by a worker when it finishes a job and is ready for more work."""
    if worker_id in _WORKER_REGISTRY:
        _WORKER_REGISTRY[worker_id]["status"] = "idle"
        _WORKER_REGISTRY[worker_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
    return {"message": "Worker marked as idle"}


@router.get("/queue-status")
def get_queue_status():
    """
    🎓 Admin endpoint: see the current state of the entire distributed system.
    Useful for debugging: are jobs stuck? Are workers idle or all busy?
    """
    idle_workers = [w for w in _WORKER_REGISTRY.values() if w["status"] == "idle"]
    busy_workers = [w for w in _WORKER_REGISTRY.values() if w["status"] == "busy"]
    return {
        "queue_depth": queue_length(),
        "total_workers": len(_WORKER_REGISTRY),
        "idle_workers": len(idle_workers),
        "busy_workers": len(busy_workers),
    }
