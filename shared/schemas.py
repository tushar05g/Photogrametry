from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobStage(str, Enum):
    IDLE = "IDLE"
    FRAME_EXTRACTION = "FRAME_EXTRACTION"
    DOWNLOAD = "DOWNLOAD"
    PREPROCESS = "PREPROCESS"
    SFM = "SFM"
    MVS = "MVS"
    MESH = "MESH"
    SPLAT = "SPLAT"
    EXPORT = "EXPORT"
    CLEANUP = "CLEANUP"

class StageStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class JobStatusResponse(BaseModel):
    job_id: str
    project_name: Optional[str] = None
    status: JobStatus
    current_stage: JobStage
    message: Optional[str] = None
    results: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: datetime

class JobResultResponse(BaseModel):
    job_id: str
    results: Dict[str, Optional[str]]
