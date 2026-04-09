from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.core.db import get_db
from backend.models.models import Job
from shared.schemas import JobStatus, JobStage, JobStatusResponse, JobResultResponse

router = APIRouter()

@router.get("/{job_id}/progress", response_model=Dict[str, Any])
def get_job_progress(job_id: str, db: Session = Depends(get_db)):
    """Granular status update for the frontend (v10.1.0)."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Map stages to human-readable progress
    stage_map = {
        JobStage.IDLE: "0% - Idle",
        JobStage.FRAME_EXTRACTION: "10% - Extracting Frames",
        JobStage.DOWNLOAD: "20% - Downloading Assets",
        JobStage.PREPROCESS: "30% - Preprocessing",
        JobStage.SFM: "50% - Structure from Motion",
        JobStage.MVS: "70% - Dense Reconstruction",
        JobStage.MESH: "85% - Meshing",
        JobStage.SPLAT: "95% - Splatting",
        JobStage.EXPORT: "100% - Completed",
        JobStage.CLEANUP: "Finalizing"
    }
    
    progress_str = stage_map.get(job.current_stage, "Processing...")
    if job.status == JobStatus.COMPLETED:
        progress_str = "100% - Ready"
    elif job.status == JobStatus.FAILED:
        progress_str = "Failed"

    # 🏁 v10.1.0: Smart Model URL Selection
    # Prioritize viewable assets for the Three.js viewer: GLB (Mesh/Splat) > PLY (Points)
    results = job.results or {}
    model_url = results.get("mesh") or results.get("model_url")
    
    if not model_url:
        # Check for Splat preview (converted to GLB for viewer compatibility)
        model_url = results.get("splat_preview_glb")
        
    if not model_url:
        # Fallback to sparse point cloud (PLY)
        model_url = results.get("sparse_pcd") or results.get("dense_pcd")
        
    # Warnings can come from any stage (MVS, MESH, etc.)
    warning = results.get("warning") or results.get("mesh_warning")
    
    return {
        "job_id": job.job_id,
        "project_name": job.project_name,
        "status": job.status.value.lower(),
        "progress": progress_str,
        "current_stage": job.current_stage.value,
        "model_url": model_url,
        "error_message": results.get("error"),
        "warnings": warning,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }

@router.post("/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running job."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.status = JobStatus.FAILED
    job.results = {"error": "Cancelled by user"}
    db.commit()
    return {"status": "cancelled", "job_id": job_id}

@router.get("/{job_id}/download")
def download_model(job_id: str, db: Session = Depends(get_db)):
    """Direct download link for the generated model."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job or not job.results:
        raise HTTPException(status_code=404, detail="Model not found")
    
    url = job.results.get("model_url") or job.results.get("mesh_url") or job.results.get("splat_url")
    if not url:
        raise HTTPException(status_code=404, detail="Download URL not available")
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=url)

@router.get("/all", response_model=Dict[str, List[Dict[str, Any]]])
def list_scans(db: Session = Depends(get_db)):
    """List all scans in the format expected by the frontend."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    # Format according to frontend expectation
    scans = []
    for job in jobs:
        results = job.results or {}
        warning = results.get("warning") or results.get("mesh_warning")
        scans.append({
            "id": job.job_id,
            "project_name": job.project_name,
            "status": job.status.value.lower(),
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "warnings": warning
        })
    return {"scans": scans}

@router.delete("/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a scan and its associated data."""
    job = db.query(Job).filter(Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.delete(job)
    db.commit()
    return {"status": "deleted", "job_id": job_id}