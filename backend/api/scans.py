from fastapi import APIRouter, HTTPException
from backend.models.models import Job
from backend.core.db import SessionLocal
from typing import Dict, Any

router = APIRouter()

@router.get("/{job_id}/status")
async def get_job_status(job_id: str):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": job.job_id,
            "status": str(job.status.value).upper(),  # COMPLETED, FAILED, IN_PROGRESS etc
            "current_stage": str(job.current_stage.value).upper(),
            "updated_at": str(job.updated_at)
        }

@router.get("/{job_id}/results")
async def get_job_results(job_id: str):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # In a real app, we'd check if COMPLETED and return the download URL
        # For now, just return placeholder URLs based on STORAGE_TYPE
        return {
            "job_id": job.job_id,
            "status": job.status,
            "model_url": f"/jobs/{job_id}/output/mesh.obj",
            "splat_url": f"/jobs/{job_id}/output/model.splat"
        }

@router.get("/")
async def list_jobs():
    with SessionLocal() as db:
        jobs = db.query(Job).all()
        return [{"job_id": j.job_id, "status": j.status} for j in jobs]