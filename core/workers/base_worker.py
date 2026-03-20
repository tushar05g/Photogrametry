"""
Base worker class for the Morphic 3D Scanner system.
"""

import os
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pathlib import Path

from core.utils.logger import get_logger


class BaseWorker(ABC):
    """
    Abstract base class for all worker implementations.
    """
    
    def __init__(self, worker_id: Optional[str] = None):
        """
        Initialize the worker.
        
        Args:
            worker_id: Unique identifier for this worker
        """
        self.worker_id = worker_id or str(uuid.uuid4())
        self.logger = get_logger(f"worker.{self.__class__.__name__}")
        self.is_running = False
        
    @abstractmethod
    def process_job(self, job_id: str, image_paths: List[str], project_name: str) -> Dict[str, Any]:
        """
        Process a 3D reconstruction job.
        
        Args:
            job_id: Unique job identifier
            image_paths: List of image file paths
            project_name: Name of the project
            
        Returns:
            Job result dictionary with status and output information
        """
        pass
    
    @abstractmethod
    def validate_inputs(self, image_paths: List[str]) -> List[str]:
        """
        Validate input images.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of validated image paths
        """
        pass
    
    def setup_workspace(self, job_id: str) -> Path:
        """
        Set up a temporary workspace for the job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Path to workspace directory
        """
        from core.utils.file_utils import ensure_directory
        
        workspace = ensure_directory(f"/tmp/morphic_{job_id}")
        self.logger.info(f"Created workspace: {workspace}")
        return workspace
    
    def cleanup_workspace(self, workspace: Path) -> None:
        """
        Clean up temporary workspace.
        
        Args:
            workspace: Workspace directory to clean
        """
        from core.utils.file_utils import safe_delete
        
        if safe_delete(workspace):
            self.logger.info(f"Cleaned up workspace: {workspace}")
        else:
            self.logger.warning(f"Failed to cleanup workspace: {workspace}")
    
    def update_job_status(self, job_id: str, status: str, progress: int = 0, 
                         message: str = "", error: Optional[str] = None) -> None:
        """
        Update job status in the database.
        
        Args:
            job_id: Job identifier
            status: Job status
            progress: Progress percentage (0-100)
            message: Status message
            error: Error message if any
        """
        try:
            from backend.core.db import SessionLocal
            from backend.models.models import ScanJob, JobStatus
            
            db = SessionLocal()
            try:
                job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
                if job:
                    job.status = JobStatus(status.lower())
                    job.progress = progress
                    if message:
                        job.warnings = message
                    if error:
                        job.error_message = error
                    db.commit()
                    self.logger.info(f"Updated job {job_id} status to {status}")
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Failed to update job status: {e}")
    
    def save_output_model(self, job_id: str, project_name: str, model_path: Path) -> str:
        """
        Save the generated 3D model to the output directory.
        
        Args:
            job_id: Job identifier
            project_name: Project name
            model_path: Path to generated model file
            
        Returns:
            URL to access the model
        """
        from core.utils.file_utils import ensure_directory
        
        output_dir = ensure_directory("output")
        model_filename = f"{job_id}_{project_name}.obj"
        output_path = output_dir / model_filename
        
        # Copy model to output directory
        import shutil
        shutil.copy2(model_path, output_path)
        
        # Return URL for frontend access
        model_url = f"/static/output/{model_filename}"
        self.logger.info(f"Model saved to: {output_path}")
        
        return model_url
    
    def run(self) -> None:
        """
        Main worker loop - to be implemented by concrete workers.
        """
        self.logger.info(f"Starting worker {self.worker_id}")
        self.is_running = True
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            self.logger.info("Worker interrupted by user")
        except Exception as e:
            self.logger.error(f"Worker crashed: {e}")
            raise
        finally:
            self.is_running = False
            self.logger.info(f"Worker {self.worker_id} stopped")
    
    @abstractmethod
    def _run_loop(self) -> None:
        """
        Main processing loop - must be implemented by concrete workers.
        """
        pass
