from sqlalchemy.dialects.postgresql import UUID
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.db import SessionLocal
from app.models import ScanJob, ScanImage, JobStatus
from app.services.cloudinary_service import upload_image_to_cloudinary
from app import schemas

router = APIRouter()

# 🎓 TEACHER'S NOTE:
# This "get_db" function is a generator. It opens a connection to Neon DB
# for each request and closes it automatically when done.
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
            is_reference="false"
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
            from app.services.image_processing import detect_coin_diameter, calculate_pixels_to_cm
            
            # Detect the coin in the first image
            diameter_px = detect_coin_diameter(first_img_url)
            
            if diameter_px:
                # Assuming a standard coin is 2.5cm
                px_per_cm = calculate_pixels_to_cm(diameter_px, 2.5)
                reference_scale_info = f"{px_per_cm:.2f} pixels/cm"
                
                # Update the image as the "reference" photo
                uploaded_images[0].is_reference = "coin"
                
                # Update the Job with the scale info
                job.reference_scale = reference_scale_info
                db.commit()
        except Exception as e:
            # We don't want to fail the whole upload if OpenCV fails
            print(f"Coin detection error: {e}")

    # 4. FINAL STEP: Release the job to Kaggle!
    job.status = JobStatus.pending
    db.commit()

    return {
        "job_id": job.id,
        "message": f"Successfully uploaded {len(files)} images. Scale: {reference_scale_info}",
        "file_count": len(files)
    }

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
    Kaggle uses this to tell us:
    1. It started processing (status="processing")
    2. It finished (status="completed" + model_url)
    3. It failed (status="failed" + error_message)
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