from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from backend.models.models import JobStatus, ReferenceType

# 🎓 TEACHER'S NOTE:
# Pydantic models (Schemas) are like "Contracts".
# They define exactly what the data should look like when it's:
# 1. Received from the user (Request)
# 2. Sent back to the user (Response)
# This prevents bad data from ever entering our system!
# 
# 🛡️ HARDENING: We now use Enums for strict validation.

class ScanImageBase(BaseModel):
    file_path: str
    is_reference: ReferenceType = ReferenceType.regular

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
    model_url: Optional[str] = None
    error_message: Optional[str] = None
    warnings: Optional[str] = None
    project_name: str = "Untitled Scan"
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

class ScanJobSummary(BaseModel):
    id: UUID
    status: JobStatus
    created_at: datetime
    project_name: str
    model_url: Optional[str] = None

    class Config:
        from_attributes = True

class ScanHistoryResponse(BaseModel):
    scans: List[ScanJobSummary]

class ScanCreateRequest(BaseModel):
    images: List[str]
    project_name: Optional[str] = "Untitled Scan"

class ScanJobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    model_url: Optional[str] = None
    error_message: Optional[str] = None
    warnings: Optional[str] = None
    project_name: Optional[str] = None
