from sqlalchemy.dialects.postgresql import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import uuid

from backend.core.db import SessionLocal
from backend.models.models import ScanJob, ScanImage, JobStatus, ReferenceType
from backend.services.cloudinary_service import upload_image_to_cloudinary
from backend.models import schemas

router = APIRouter()

from backend.core.db import SessionLocal, get_db

def validate_cloudinary_url(url: str):
    """🛡️ SSRF PROTECTION: Ensures the URL is actually from our Cloudinary account."""
    from backend.core.config import CLOUDINARY_CLOUD_NAME
    if not url.startswith(f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/"):
        raise HTTPException(
            status_code=400, 
            detail=f"Security Alert: Blocked unauthorized image source"
        )
    return True

@router.post("/upload", response_model=schemas.UploadResponse)
async def upload_scans(
    files: List[UploadFile] = File(...), 
    db: Session = Depends(get_db)
):
    """
    Step 1: Create a new ScanJob.
    Step 2: Upload each photo to Cloudinary.
    Step 3: Save the record in the ScanImage table.
    """
    # 1. Cancel previous active jobs (Auto-cleanup on reload/new scan)
    db.query(ScanJob).filter(
        ScanJob.status.in_([
            JobStatus.pending, 
            JobStatus.processing, 
            JobStatus.uploading, 
            JobStatus.initializing
        ])
    ).update({"status": JobStatus.cancelled}, synchronize_session=False)
    db.commit()

    # 2. Start a New Job
    job = ScanJob(status=JobStatus.initializing)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Update to 'uploading' before the cloud loop
    job.status = JobStatus.uploading
    db.commit()

    # 2. Parallel Upload to Cloudinary
    import asyncio
    
    # helper for parallel work
    async def upload_and_save(file_obj):
        image_url = await upload_image_to_cloudinary(file_obj.file)
        new_img = ScanImage(
            job_id=job.id,
            file_path=image_url,
            is_reference=ReferenceType.regular
        )
        return new_img

    # Kick off all uploads at once!
    tasks = [upload_and_save(f) for f in files]
    uploaded_images = await asyncio.gather(*tasks)
    
    # Save all records to DB
    for img in uploaded_images:
        db.add(img)
    db.commit()

    # 3. NEW: Automatic Scaling (Coin Detection)
    # We try to find the coin in the VERY FIRST photo uploaded.
    reference_scale_info = "Not detected"
    if uploaded_images:
        first_img_url = uploaded_images[0].file_path
        try:
            from backend.services.image_processing import detect_coin_diameter, calculate_pixels_to_cm
            
            # Detect the coin in the first image
            diameter_px = detect_coin_diameter(first_img_url)
            
            if diameter_px:
                # Assuming a standard coin is 2.5cm
                px_per_cm = calculate_pixels_to_cm(diameter_px, 2.5)
                reference_scale_info = f"{px_per_cm:.2f} pixels/cm"
                
                # Update the image as the "reference" photo
                uploaded_images[0].is_reference = ReferenceType.coin
                
                # Update the Job with the scale info
                job.reference_scale = reference_scale_info
                db.commit()
        except Exception as e:
            # We don't want to fail the whole upload if OpenCV fails
            print(f"Coin detection error: {e}")

    # 4. FINAL STEP: Release the job to Redis queue!
    from backend.queue.manager import enqueue_job
    job.status = JobStatus.pending
    db.commit()
    enqueue_job(str(job.id))  # Push to Redis queue instead of HTTP polling

    return {
        "job_id": job.id,
        "message": f"Successfully uploaded {len(files)} images. Scale: {reference_scale_info}",
        "file_count": len(files)
    }

def background_coin_detect(job_id: uuid.UUID, first_img_url: str, session_factory):
    db = session_factory()
    try:
        from backend.services.image_processing import detect_coin_diameter, calculate_pixels_to_cm
        diameter_px = detect_coin_diameter(first_img_url)
        if diameter_px:
            px_per_cm = calculate_pixels_to_cm(diameter_px, 2.5)
            job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
            if job:
                job.reference_scale = f"{px_per_cm:.2f} pixels/cm"
                first_img = db.query(ScanImage).filter(ScanImage.job_id == job_id).order_by(ScanImage.created_at).first()
                if first_img:
                    first_img.is_reference = ReferenceType.coin
                db.commit()
    except Exception as e:
        print(f"Coin detection error: {e}")
    finally:
        db.close()

@router.get("/upload-params")
def get_upload_params():
    """Returns signed parameters for the frontend to upload safely."""
    from backend.services.cloudinary_service import generate_upload_params
    return generate_upload_params()

@router.post("/create_from_urls", response_model=schemas.UploadResponse)
def create_job_from_urls(
    payload: schemas.ScanCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    🎓 TEACHER'S NOTE: The main job creation endpoint.
    
    Flow:
    1. Validate images (blur, resolution, duplicates).
    2. Create a DB record.
    3. Push job ID to Redis queue so a worker can pick it up.
    """
    from backend.services.validation import validate_dataset
    from backend.queue.manager import enqueue_job

    # --- STEP 1: Validate the dataset BEFORE creating any DB records ---
    validation_result = validate_dataset(payload.images)
    if not validation_result["valid"]:
        # JOIN the errors into a single string to avoid [object Object] issues
        error_msg = " | ".join(validation_result["errors"])
        raise HTTPException(
            status_code=422,
            detail=f"Validation Failed: {error_msg}"
        )

    # --- STEP 2: Cancel previous active jobs (auto-cleanup) ---
    db.query(ScanJob).filter(
        ScanJob.status.in_([
            JobStatus.pending,
            JobStatus.processing,
            JobStatus.uploading,
            JobStatus.initializing
        ])
    ).update({"status": JobStatus.cancelled}, synchronize_session=False)
    db.commit()

    # --- STEP 3: Create the new job ---
    job = ScanJob(status=JobStatus.pending, project_name=payload.project_name)
    if validation_result.get("warnings"):
        job.warnings = " | ".join(validation_result["warnings"])
    db.add(job)
    db.commit()
    db.refresh(job)

    # --- STEP 4: Create image records ---
    for url in payload.images:
        validate_cloudinary_url(url)
        new_img = ScanImage(job_id=job.id, file_path=url, is_reference=ReferenceType.regular)
        db.add(new_img)
    db.commit()

    # --- STEP 5: Push job to Redis queue ---
    # 🎓 This is the KEY distributed step. Instead of directly calling the worker,
    # we add it to a queue. An idle worker will pick it up automatically.
    enqueue_job(str(job.id))

    # --- STEP 6: Background coin detection (does not block the response) ---
    if payload.images:
        background_tasks.add_task(background_coin_detect, job.id, payload.images[0], SessionLocal)

    return {
        "job_id": job.id,
        "message": f"Job queued. Validation passed with {len(validation_result.get('warnings', []))} warning(s).",
        "file_count": len(payload.images)
    }

@router.delete("/{job_id}")
def delete_scan(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deletes a scan and all its images from the DB."""
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.delete(job)
    db.commit()
    return {"message": "Scan deleted successfully"}

@router.get("/next-pending", response_model=schemas.ScanJobResponse)
def get_next_pending_job(db: Session = Depends(get_db)):
    """
    Kaggle uses this to find the oldest job that is still 'pending'.
    """
    job = (
        db.query(ScanJob)
        .filter(ScanJob.status == JobStatus.pending)
        .order_by(ScanJob.created_at.asc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No pending jobs found")
    return job

@router.get("/{job_id}/images", response_model=schemas.ScanImageList)
def get_job_images(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Kaggle uses this to get the list of Cloudinary URLs to download.
    """
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    image_urls = [img.file_path for img in job.images]
    return {"job_id": job_id, "images": image_urls}

@router.patch("/{job_id}", response_model=schemas.ScanJobResponse)
def update_job(
    job_id: uuid.UUID, 
    update_data: schemas.ScanJobUpdate, 
    db: Session = Depends(get_db)
):
    """
    Kaggle uses this to tell us status updates.
    """
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if update_data.status:
        job.status = update_data.status
    if update_data.model_url:
        job.model_url = update_data.model_url
    if update_data.error_message:
        job.error_message = update_data.error_message
    if update_data.warnings:
        job.warnings = update_data.warnings
    if update_data.project_name:
        job.project_name = update_data.project_name
    if update_data.progress:
        job.progress = update_data.progress

    db.commit()
    db.refresh(job)
    return job

@router.post("/{job_id}/cancel", response_model=schemas.ScanJobResponse)
def cancel_scan(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Cancels an active scan job.
    """
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status in [JobStatus.completed, JobStatus.failed]:
        return job

    job.status = JobStatus.cancelled
    db.commit()
    db.refresh(job)
    return job

@router.get("/{job_id}", response_model=schemas.ScanJobResponse)
def get_scan(job_id: uuid.UUID, db: Session = Depends(get_db)):
    # Look for the job in the database
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job

@router.get("/", response_model=schemas.ScanHistoryResponse)
def list_scans(db: Session = Depends(get_db)):
    """
    Returns ALL scans in the database. 
    In the future, this would be filtered by current_user.
    """
    scans = db.query(ScanJob).order_by(ScanJob.created_at.desc()).all()
    return {"scans": scans}