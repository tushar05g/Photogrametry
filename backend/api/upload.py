import os
import asyncio
import uuid
import shutil
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pathlib import Path
from backend.config import settings
from storage.factory import get_storage_provider
from shared.schemas import JobStatusResponse, JobStatus, JobStage
from worker.pipeline.tasks import initiate_pipeline
from backend.core.db import SessionLocal
from backend.models.models import Job

logger = logging.getLogger(__name__)
router = APIRouter()

UNTITLED_SCAN = "Untitled Scan"

@router.post("/init", response_model=JobStatusResponse)
async def init_job(project_name: str = Form(UNTITLED_SCAN)):
    job_id = str(uuid.uuid4())
    with SessionLocal() as db:
        new_job = Job(
            job_id=job_id,
            project_name=project_name,
            status=JobStatus.PENDING,
            current_stage=JobStage.IDLE,
            is_video=False
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return JobStatusResponse(
            job_id=job_id,
            project_name=new_job.project_name,
            status=new_job.status,
            current_stage=new_job.current_stage,
            created_at=new_job.created_at,
            updated_at=new_job.updated_at
        )

@router.post("/{job_id}/upload-single")
async def upload_single_image(job_id: str, file: UploadFile = File(...)):
    storage = get_storage_provider()
    try:
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

        file_bytes = await file.read()
        remote_path = f"jobs/{job_id}/input/{file.filename}"

        # Use async upload to avoid blocking the event loop
        if hasattr(storage, "upload_file_async"):
            await storage.upload_file_async(remote_path, file_bytes)
        else:
            storage.upload_file(remote_path, file_bytes)

        return {"status": "success", "filename": file.filename, "size": len(file_bytes)}
    except Exception as e:
        logger.error(f"Single upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/start")
async def start_pipeline(job_id: str):
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        initiate_pipeline.apply_async(
            kwargs={"job_id": job_id, "enable_splat": True},
            task_id=job_id
        )
        return {"status": "started", "job_id": job_id}

@router.post("/upload", response_model=JobStatusResponse)
async def upload_images(
    project_name: str = Form(UNTITLED_SCAN),
    files: List[UploadFile] = File(...)
):
    if len(files) < settings.MIN_IMAGES_PER_JOB:
        raise HTTPException(status_code=400, detail=f"Minimum {settings.MIN_IMAGES_PER_JOB} images required")
    
    if len(files) > settings.MAX_IMAGES_PER_JOB:
        raise HTTPException(status_code=400, detail=f"Maximum {settings.MAX_IMAGES_PER_JOB} images allowed")

    job_id = str(uuid.uuid4())
    logger.info(f"Creating job {job_id} with {len(files)} images")

    # 1. Create Job in DB
    with SessionLocal() as db:
        new_job = Job(
            job_id=job_id, 
            project_name=project_name,
            status=JobStatus.PENDING, 
            current_stage=JobStage.IDLE,
            is_video=False
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)

    # 2. Upload to Storage directly from memory (avoid temp file race condition)
    storage = get_storage_provider()

    try:
        for idx, file in enumerate(files):
            fname = f"img_{idx:03d}{Path(file.filename).suffix}"
            remote_path = f"jobs/{job_id}/input/{fname}"
            
            # Read file bytes into memory and upload directly
            file_bytes = await file.read()
            if hasattr(storage, "upload_file_async"):
                await storage.upload_file_async(remote_path, file_bytes)
            else:
                await asyncio.to_thread(storage.upload_file, remote_path, file_bytes)
            logger.info(f"Uploaded {fname} ({len(file_bytes)} bytes) to {remote_path}")

        # 3. Trigger Pipeline Chain
        initiate_pipeline.apply_async(
            kwargs={"job_id": job_id, "enable_splat": True},
            task_id=job_id
        )

        return JobStatusResponse(
            job_id=job_id,
            project_name=new_job.project_name,
            status=new_job.status,
            current_stage=new_job.current_stage,
            message="Images uploaded and job initiated.",
            created_at=new_job.created_at,
            updated_at=new_job.updated_at
        )

    except Exception as e:
        logger.error(f"Upload failed for job {job_id}: {e}")
        # Mark as failed in DB
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-video", response_model=JobStatusResponse)
async def upload_videos(
    project_name: str = Form(UNTITLED_SCAN),
    files: List[UploadFile] = File(...)
):
    # For videos, we don't have a strict MIN count yet, but at least 1
    if not files:
        raise HTTPException(status_code=400, detail="At least one video required")

    job_id = str(uuid.uuid4())
    logger.info(f"Creating video job {job_id} with {len(files)} videos")

    # 1. Create Job in DB
    with SessionLocal() as db:
        new_job = Job(
            job_id=job_id, 
            project_name=project_name,
            status=JobStatus.PENDING, 
            current_stage=JobStage.IDLE,
            is_video=True
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)

    # 2. Upload to Storage
    storage = get_storage_provider()

    try:
        for idx, file in enumerate(files):
            fname = f"video_{idx:03d}{Path(file.filename).suffix}"
            remote_path = f"jobs/{job_id}/videos/{fname}"
            
            file_bytes = await file.read()
            if hasattr(storage, "upload_file_async"):
                await storage.upload_file_async(remote_path, file_bytes)
            else:
                await asyncio.to_thread(storage.upload_file, remote_path, file_bytes)
            logger.info(f"Uploaded {fname} ({len(file_bytes)} bytes) to {remote_path}")

        # 3. Trigger Pipeline Chain (Starting with FRAME_EXTRACTION)
        initiate_pipeline.apply_async(
            kwargs={"job_id": job_id, "enable_splat": True},
            task_id=job_id
        )

        return JobStatusResponse(
            job_id=job_id,
            project_name=new_job.project_name,
            status=new_job.status,
            current_stage=new_job.current_stage,
            message="Videos uploaded and job initiated.",
            created_at=new_job.created_at,
            updated_at=new_job.updated_at
        )

    except Exception as e:
        logger.error(f"Video upload failed for job {job_id}: {e}")
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                db.commit()
        raise HTTPException(status_code=500, detail=str(e))
