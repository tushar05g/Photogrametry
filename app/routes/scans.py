from sqlalchemy import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ScanJob

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def create_scan(db: Session = Depends(get_db)):
    job = ScanJob()
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "status": job.status}

@router.get("/{job_id}")
def get_scan(job_id : UUID,db : Session = Depends(get_db)):
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job.id, "status": job.status, "created_at" : job.created_at}