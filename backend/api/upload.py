from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
import os
import tempfile
import shutil
from pathlib import Path

from backend.core.db import SessionLocal, get_db
from backend.models.models import ScanJob, ScanImage, JobStatus, ReferenceType
from backend.models import schemas
from backend.services.cloudinary_service import upload_image_to_cloudinary
from backend.task_queue.manager import enqueue_job

router = APIRouter()

@router.post("/images", response_model=schemas.UploadResponse)
async def upload_images_direct(
    files: List[UploadFile] = File(...),
    project_name: str = "Untitled Scan",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Direct image upload endpoint for frontend integration.
    Processes images locally without Cloudinary for faster development.
    
    Flow:
    1. Save uploaded images to temporary storage
    2. Validate image quality and quantity
    3. Create job in database
    4. Queue job for CPU photogrammetry processing
    5. Return job ID for tracking
    """
    
    # Validate file count
    if len(files) < 3:
        raise HTTPException(
            status_code=400,
            detail="Minimum 3 images required for 3D reconstruction"
        )
    
    if len(files) > 50:
        raise HTTPException(
            status_code=400,
            detail="Maximum 50 images allowed per job"
        )
    
    # Cancel previous active jobs (auto-cleanup)
    db.query(ScanJob).filter(
        ScanJob.status.in_([
            JobStatus.pending, 
            JobStatus.processing, 
            JobStatus.uploading, 
            JobStatus.initializing
        ])
    ).update({"status": JobStatus.cancelled}, synchronize_session=False)
    db.commit()
    
    # Create new job
    job = ScanJob(status=JobStatus.initializing, project_name=project_name)
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Create temporary directory for images
    temp_dir = tempfile.mkdtemp(prefix=f"scan_{job.id}_")
    image_paths = []
    
    try:
        # Save uploaded files
        job.status = JobStatus.uploading
        db.commit()
        
        for i, file in enumerate(files):
            # Validate file type
            if not file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is not an image"
                )
            
            # Validate file size (max 10MB per image)
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset to start
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} is too large (max 10MB)"
                )
            
            # Save file
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in ['.jpg', '.jpeg', '.png', '.webp']:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file_ext}"
                )
            
            filename = f"image_{i+1:03d}{file_ext}"
            file_path = os.path.join(temp_dir, filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            image_paths.append(file_path)
        
        # Validate images with CPU pipeline
        try:
            from core.photogrammetry import PhotogrammetryPipeline
            pipeline = PhotogrammetryPipeline()
            
            # Quick validation without full processing
            validated_paths = pipeline.validate_and_fix_paths(image_paths)
            quality_paths = pipeline.validate_image_quality(validated_paths)
            
            if len(quality_paths) < 3:
                raise ValueError("Insufficient valid images after quality check")
            
            # Update job with validated paths
            job.status = JobStatus.pending
            job.warnings = f"Validated {len(quality_paths)}/{len(image_paths)} images"
            db.commit()
            
            # Queue job for processing
            enqueue_job(str(job.id), quality_paths, project_name)
            
            # Store image paths in database for reference
            for path in quality_paths:
                img_record = ScanImage(
                    job_id=job.id,
                    file_path=path,  # Local path for worker
                    is_reference=ReferenceType.regular
                )
                db.add(img_record)
            db.commit()
            
            return {
                "job_id": job.id,
                "message": f"Successfully uploaded {len(files)} images. {len(quality_paths)} passed validation.",
                "file_count": len(quality_paths),
                "warnings": job.warnings
            }
            
        except Exception as e:
            job.status = JobStatus.failed
            job.error_message = str(e)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Image validation failed: {str(e)}"
            )
            
    except Exception as e:
        # Cleanup on error
        job.status = JobStatus.failed
        job.error_message = str(e)
        db.commit()
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    
    finally:
        # Note: Don't cleanup temp_dir here as worker needs it
        # Worker will cleanup after processing
        pass

@router.post("/images-url", response_model=schemas.UploadResponse)
async def upload_images_from_urls(
    request: schemas.ScanCreateRequest,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Alternative endpoint for images provided as URLs (Cloudinary or local paths).
    Uses the existing validation and queue system.
    """
    from backend.services.validation import validate_dataset
    
    # Validate the dataset
    validation_result = validate_dataset(request.images)
    if not validation_result["valid"]:
        error_msg = " | ".join(validation_result["errors"])
        raise HTTPException(
            status_code=422,
            detail=f"Validation Failed: {error_msg}"
        )
    
    # Cancel previous active jobs
    db.query(ScanJob).filter(
        ScanJob.status.in_([
            JobStatus.pending,
            JobStatus.processing,
            JobStatus.uploading,
            JobStatus.initializing
        ])
    ).update({"status": JobStatus.cancelled}, synchronize_session=False)
    db.commit()
    
    # Create new job
    job = ScanJob(
        status=JobStatus.pending, 
        project_name=request.project_name,
        warnings=" | ".join(validation_result.get("warnings", []))
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # Create image records
    for url in request.images:
        # Validate URL (SSRF protection)
        if url.startswith("/") or os.path.exists(url):
            # Local file path
            pass
        else:
            # Cloudinary URL validation
            from backend.core.config import CLOUDINARY_CLOUD_NAME
            if not url.startswith(f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/"):
                raise HTTPException(
                    status_code=400,
                    detail="Unauthorized image source"
                )
        
        img_record = ScanImage(
            job_id=job.id,
            file_path=url,
            is_reference=ReferenceType.regular
        )
        db.add(img_record)
    db.commit()
    
    # Queue job
    enqueue_job(str(job.id), request.images, request.project_name)
    
    return {
        "job_id": job.id,
        "message": f"Job queued with {len(request.images)} images.",
        "file_count": len(request.images),
        "warnings": job.warnings
    }

@router.get("/job/{job_id}/download")
async def download_model(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Download the generated 3D model file.
    """
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.completed:
        raise HTTPException(
            status_code=400,
            detail="Job not completed yet"
        )
    
    if not job.model_url:
        raise HTTPException(
            status_code=404,
            detail="Model file not available"
        )
    
    # Return file for download
    from fastapi.responses import FileResponse
    
    if job.model_url.startswith("/static/"):
        # Local file
        file_path = job.model_url.replace("/static/", "")
        full_path = os.path.join(os.getcwd(), file_path)
        
        if not os.path.exists(full_path):
            raise HTTPException(
                status_code=404,
                detail="Model file not found on server"
            )
        
        return FileResponse(
            full_path,
            media_type="application/octet-stream",
            filename=f"{job.project_name}_{job_id}.obj"
        )
    else:
        # Cloudinary URL - redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(job.model_url)
