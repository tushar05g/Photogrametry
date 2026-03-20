"""
CPU Photogrammetry Worker for the Morphic 3D Scanner system.
"""

import os
import time
import logging
import shutil
from typing import Dict, Any, List
from pathlib import Path

from core.workers.base_worker import BaseWorker
from core.photogrammetry import PhotogrammetryPipeline
from core.utils.logger import get_logger


class CPUPhotogrammetryWorker(BaseWorker):
    """
    CPU-based photogrammetry worker that processes 3D reconstruction jobs
    using the CPU photogrammetry pipeline.
    """
    
    def __init__(self, worker_id: str = None, output_dir: str = None):
        """
        Initialize the CPU worker.
        
        Args:
            worker_id: Unique worker identifier
            output_dir: Output directory for generated models
        """
        super().__init__(worker_id)
        self.output_dir = output_dir or os.getenv("OUTPUT_DIR", os.path.abspath("output"))
        self.pipeline = None
        
        # Ensure output directory exists
        from core.utils.file_utils import ensure_directory
        ensure_directory(self.output_dir)
    
    def process_job(self, job_id: str, image_paths: List[str], project_name: str) -> Dict[str, Any]:
        """
        Process a 3D reconstruction job using CPU photogrammetry.
        
        Args:
            job_id: Unique job identifier
            image_paths: List of image file paths
            project_name: Name of the project
            
        Returns:
            Job result dictionary with status and output information
        """
        workspace = None
        try:
            self.logger.info(f"🚀 Starting job {job_id} for project: {project_name}")
            
            # Update status to processing
            self.update_job_status(job_id, "processing", 10, "Starting photogrammetry pipeline")
            
            # Set up workspace
            workspace = self.setup_workspace(job_id)
            
            # Validate inputs
            validated_paths = self.validate_inputs(image_paths)
            self.update_job_status(job_id, "processing", 20, f"Validated {len(validated_paths)} images")
            
            # Initialize and run photogrammetry pipeline
            self.pipeline = PhotogrammetryPipeline()
            self.pipeline.workspace = str(workspace)
            
            result = self.pipeline.run_pipeline(validated_paths, project_name)
            
            if result["status"] == "success":
                # Save model to output directory
                model_path = Path(result["final_mesh"])
                model_url = self.save_output_model(job_id, project_name, model_path)
                
                # Update job with success
                self.update_job_status(
                    job_id, 
                    "completed", 
                    100, 
                    f"Generated {result['validation']['vertices']} vertices, {result['validation']['triangles']} triangles"
                )
                
                self.logger.info(f"✅ Job {job_id} completed successfully")
                return {
                    "status": "success",
                    "job_id": job_id,
                    "model_url": model_url,
                    "vertices": result["validation"]["vertices"],
                    "triangles": result["validation"]["triangles"],
                    "processing_time": result["processing_time"]
                }
            else:
                raise Exception(f"Pipeline failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"❌ Job {job_id} failed: {e}")
            self.update_job_status(job_id, "failed", 0, "", str(e))
            
            return {
                "status": "failed",
                "job_id": job_id,
                "error": str(e)
            }
        finally:
            # Cleanup workspace
            if workspace:
                self.cleanup_workspace(workspace)
    
    def validate_inputs(self, image_paths: List[str]) -> List[str]:
        """
        Validate input images using the photogrammetry pipeline.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of validated image paths
        """
        if not self.pipeline:
            self.pipeline = PhotogrammetryPipeline()
        
        # Use pipeline's validation methods
        validated_paths = self.pipeline.validate_and_fix_paths(image_paths)
        quality_paths = self.pipeline.validate_image_quality(validated_paths)
        
        if len(quality_paths) < 3:
            raise ValueError(f"Insufficient valid images: {len(quality_paths)} (minimum 3 required)")
        
        self.logger.info(f"✅ Validated {len(quality_paths)}/{len(image_paths)} images")
        return quality_paths
    
    def _run_loop(self) -> None:
        """
        Main processing loop for Redis queue-based worker.
        """
        import redis
        from rq import Worker, Queue
        from rq.job import Job
        
        # Connect to Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        conn = redis.from_url(redis_url)
        
        # Start worker
        queue = Queue('morphic_cpu_queue', connection=conn)
        worker = Worker([queue], connection=conn)
        
        self.logger.info("🔄 Starting Redis queue worker loop")
        
        # Work on jobs
        worker.work()


# Legacy function for backward compatibility
def process_3d_model(job_id: str, image_paths: List[str], project_name: str) -> str:
    """
    Legacy function for backward compatibility with existing code.
    
    Args:
        job_id: Job identifier
        image_paths: List of image paths
        project_name: Project name
        
    Returns:
        Path to generated model file
    """
    worker = CPUPhotogrammetryWorker()
    result = worker.process_job(job_id, image_paths, project_name)
    
    if result["status"] == "success":
        # Return the file path for legacy compatibility
        return os.path.join(worker.output_dir, f"{job_id}_{project_name}.obj")
    else:
        raise Exception(result["error"])


if __name__ == "__main__":
    # Run worker when executed directly
    worker = CPUPhotogrammetryWorker()
    worker.run()
