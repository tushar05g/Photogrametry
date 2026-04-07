import logging
import json
import redis
from typing import Optional
from datetime import datetime
from backend.core.db import SessionLocal
from backend.models.models import Job, Stage
from shared.schemas import JobStatus, JobStage, StageStatus
from backend.config import settings

logger = logging.getLogger(__name__)

# Redis for WebSocket broadcasting
redis_client = redis.from_url(settings.REDIS_URL)

def _broadcast(job_id: str, data: dict):
    try:
        redis_client.publish(f"job_status:{job_id}", json.dumps(data, default=str))
    except Exception as e:
        logger.warning(f"Failed to publish to Redis: {e}")

def update_job_status(job_id: str, status: JobStatus = None, current_stage: JobStage = None):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            if status:
                job.status = status
            if current_stage:
                job.current_stage = current_stage
            db.commit()
            
            _broadcast(job_id, {
                "job_id": job_id,
                "status": job.status,
                "current_stage": job.current_stage,
                "updated_at": job.updated_at
            })

def start_stage(job_id: str, stage_name: JobStage):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.current_stage = stage_name
            job.status = JobStatus.IN_PROGRESS
        
        stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == stage_name).first()
        if not stage:
            stage = Stage(job_id=job_id, stage_name=stage_name)
            db.add(stage)
        
        stage.status = StageStatus.IN_PROGRESS
        stage.start_time = datetime.now()
        stage.error_message = None
        db.commit()
        
        _broadcast(job_id, {
            "job_id": job_id,
            "status": JobStatus.IN_PROGRESS,
            "current_stage": stage_name,
            "stage_status": StageStatus.IN_PROGRESS
        })

def complete_stage(job_id: str, stage_name: JobStage):
    with SessionLocal() as db:
        stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == stage_name).first()
        if stage:
            stage.status = StageStatus.COMPLETED
            stage.end_time = datetime.now()
            db.commit()
            
            _broadcast(job_id, {
                "job_id": job_id,
                "current_stage": stage_name,
                "stage_status": StageStatus.COMPLETED
            })

def fail_stage(job_id: str, stage_name: JobStage, error_message: str):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
        
        stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == stage_name).first()
        if stage:
            stage.status = StageStatus.FAILED
            stage.end_time = datetime.now()
            stage.error_message = error_message
        db.commit()
        
        _broadcast(job_id, {
            "job_id": job_id,
            "status": JobStatus.FAILED,
            "current_stage": stage_name,
            "stage_status": StageStatus.FAILED,
            "error": error_message
        })
def is_stage_completed(job_id: str, stage_name: JobStage) -> bool:
    with SessionLocal() as db:
        stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == stage_name).first()
        return stage is not None and stage.status == StageStatus.COMPLETED

def get_last_completed_stage(job_id: str) -> Optional[JobStage]:
    with SessionLocal() as db:
        stages = db.query(Stage).filter(Stage.job_id == job_id, Stage.status == StageStatus.COMPLETED).all()
        if not stages:
            return None
        # We assume stages follow the pipeline order. Let's find the one with latest end_time
        return max(stages, key=lambda s: s.end_time or datetime.min).stage_name
