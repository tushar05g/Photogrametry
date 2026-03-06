from sqlalchemy import Column, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from .db import Base
from enum import Enum

# NEW IMPORTS FOR RELATIONSHIPS
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey

class JobStatus(str, Enum):
    initializing = "initializing"
    uploading = "uploading"
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status = Column(SQLEnum(JobStatus), default=JobStatus.pending)
    input_path = Column(String, nullable=True)
    output_model_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # NEW COLUMN: Scaling info (e.g., "1 coin = 2cm")
    reference_scale = Column(String, nullable=True) 
    model_url = Column(String, nullable=True) # 👈 For the final 3D file
    error_message = Column(Text, nullable=True) # 👈 To help us debug failures

    # NEW RELATIONSHIP: This lets us say `job.images` in Python
    # back_populates="job" means the ScanImage class has a variable called `job` that points back here.
    images = relationship("ScanImage", back_populates="job", cascade="all, delete-orphan")


# NEW TABLE: To store individual uploaded photos
class ScanImage(Base):
    __tablename__ = "scan_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_path = Column(String, nullable=False) # This will be the Cloudinary URL
    
    # NEW COLUMN: True/False if this is the "coin" image
    is_reference = Column(String, default="false") 
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # THE FOREIGN KEY: This connects the image to the specific job (as you correctly explained!)
    job_id = Column(UUID(as_uuid=True), ForeignKey("scan_jobs.id"))

    # THE RELATIONSHIP: This lets us say `image.job` in Python to get the ScanJob it belongs to
    job = relationship("ScanJob", back_populates="images")

