from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.models import JobStatus

# 🎓 TEACHER'S NOTE:
# Pydantic models (Schemas) are like "Contracts".
# They define exactly what the data should look like when it's:
# 1. Received from the user (Request)
# 2. Sent back to the user (Response)
# This prevents bad data from ever entering our system!

class ScanImageBase(BaseModel):
    file_path: str
    is_reference: str = "false"

class ScanImageResponse(ScanImageBase):
    id: UUID
    job_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True # This tells Pydantic to work with SQLAlchemy models

class ScanJobResponse(BaseModel):
    id: UUID
    status: JobStatus
    created_at: datetime
    images: List[ScanImageResponse] = []

    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    job_id: UUID
    message: str
    file_count: int

class ScanImageList(BaseModel):
    job_id: UUID
    images: List[str] # Just the URLs

class ScanJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    model_url: Optional[str] = None
    error_message: Optional[str] = None
