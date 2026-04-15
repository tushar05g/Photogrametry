from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import logging
import os

from backend.core.db import get_db
from backend.models.models import Job, Stage
from shared.schemas import JobStatus, JobStage, StageStatus
from backend.config import settings

router = APIRouter(prefix="/worker", tags=["Worker API"])
logger = logging.getLogger(__name__)

# v10.4.0: Pull-based architecture for Kaggle/Colab workers
WORKER_TOKEN = os.getenv("WORKER_TOKEN", "test-token-123")

def verify_worker(x_worker_token: str = Header(...)):
    if x_worker_token != WORKER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker token"
        )

@router.post("/poll")
def poll_job(
    worker_id: str,
    db: Session = Depends(get_db),
    _ = Depends(verify_worker)
):
    """
    Kaggle worker calls this to find work.
    We look for jobs stuck in 'SFM' stage with 'PENDING' status.
    """
    # Find jobs that need GPU (SFM, MVS, or MESH) and are PENDING in that stage
    job = db.query(Job).join(Stage).filter(
        Job.status == JobStatus.IN_PROGRESS,
        Stage.stage_name == JobStage.SFM,
        Stage.status == StageStatus.PENDING
    ).order_by(Job.created_at.asc()).first()

    if not job:
        return {"job_id": None}

    # Mark the stage as IN_PROGRESS
    sfm_stage = next((s for s in job.stages if s.stage_name == JobStage.SFM), None)
    if sfm_stage:
        sfm_stage.status = StageStatus.IN_PROGRESS
        sfm_stage.start_time = datetime.now()
        db.commit()

    # Determine input assets
    # In Phase 2, we assume images are already preprocessed and in Cloudinary
    # The worker needs the job_id to know prefix
    return {
        "job_id": job.job_id,
        "is_video": job.is_video,
        "project_name": job.project_name,
        "current_stage": job.current_stage
    }

class StageUpdateRequest(BaseModel):
    stage_name: JobStage
    status: StageStatus
    error_message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None

@router.post("/{job_id}/stage")
def update_stage(
    job_id: str,
    update: StageUpdateRequest,
    db: Session = Depends(get_db),
    _ = Depends(verify_worker)
):
    """
    Update the status of a specific stage.
    """
    stage_name = update.stage_name
    status = update.status
    error_message = update.error_message
    results = update.results

    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stage = db.query(Stage).filter(
        Stage.job_id == job_id,
        Stage.stage_name == stage_name
    ).first()

    if not stage:
        # Create stage if it doesn't exist (e.g. for dynamic stages)
        stage = Stage(job_id=job_id, stage_name=stage_name)
        db.add(stage)

    stage.status = status
    if status == StageStatus.IN_PROGRESS:
        stage.start_time = datetime.now()
    elif status in [StageStatus.COMPLETED, StageStatus.FAILED]:
        stage.end_time = datetime.now()
        stage.error_message = error_message

    if results:
        if job.results:
            job.results.update(results)
        else:
            job.results = results

    # Sync Job current_stage
    job.current_stage = stage_name
    if status == StageStatus.FAILED:
        job.status = JobStatus.FAILED
    
    db.commit()
    return {"status": "success"}

@router.post("/{job_id}/complete")
def complete_job(
    job_id: str,
    results: Dict[str, Any],
    db: Session = Depends(get_db),
    _ = Depends(verify_worker)
):
    """
    Finalize the job when MESH (or last GPU stage) is done.
    """
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job.results = results
    job.status = JobStatus.COMPLETED
    job.current_stage = JobStage.CLEANUP
    db.commit()

    # 🏁 v10.4.3: Trigger final Celery tasks to resume orchestration
    try:
        from worker.pipeline.tasks import task_cleanup_assets
        task_cleanup_assets.delay(job_id)
        logger.info(f"📡 Triggered final cleanup for job {job_id}")
    except Exception as e:
        logger.error(f"⚠️ Failed to trigger cleanup task: {e}")

    return {"status": "success"}
