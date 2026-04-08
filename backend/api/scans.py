from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.db import get_db
from backend.models.models import Job
from shared.schemas import JobStatusResponse, JobResultResponse

router = APIRouter()

@router.get("/", response_model=List[JobStatusResponse])
def list_jobs(db: Session = Depends(get_db)):
    """List all photogrammetry jobs."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return jobs

@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get details of a specific job."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get the current status and stage of a job."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/{job_id}/results", response_model=JobResultResponse)
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    """Get the reconstruction results (URLs) for a job."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResultResponse(
        job_id=job.job_id,
        results=job.results or {}
    )