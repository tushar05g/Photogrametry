import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, JSON, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.core.db import Base
from shared.schemas import JobStatus, JobStage, StageStatus

class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_name = Column(String(100), nullable=True)
    status = Column(SQLEnum(JobStatus), default=JobStatus.PENDING, index=True)
    current_stage = Column(SQLEnum(JobStage), default=JobStage.IDLE, index=True)
    is_video = Column(Boolean, default=False)
    results = Column(JSON, nullable=True)
    quality_report = Column(JSON, nullable=True)
    
    # Time Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    
    # Relationships
    stages = relationship("Stage", back_populates="job", cascade="all, delete-orphan")

class Stage(Base):
    __tablename__ = "stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("jobs.job_id"), nullable=False)
    stage_name = Column(SQLEnum(JobStage), nullable=False)
    status = Column(SQLEnum(StageStatus), default=StageStatus.PENDING)
    
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(String, nullable=True)

    job = relationship("Job", back_populates="stages")
