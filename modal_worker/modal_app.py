import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional
import modal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🏁 v8.2.0: Granular GPU Workers with Storage Abstraction
app = modal.App(name="photogrammetry-worker")
# Volume is still useful as a cache or for ModalStorageProvider
volume = modal.Volume.from_name("morphic-scan-data")

image = (
    modal.Image.from_registry("colmap/colmap:latest", add_python="3.10")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "boto3",
        "pydantic-settings",
        "opencv-python-headless",
        "numpy",
        "requests",
        "psutil",
        "scikit-image",
        "scikit-learn",
        "pymeshlab",
        "trimesh",
        "rembg",
        "cloudinary"
    )
    .add_local_python_source("modal_worker")
    .add_local_python_source("storage")
    .add_local_python_source("shared")
    .add_local_python_source("backend")
)

secret = modal.Secret.from_name("photogrammetry-env")
GPU_TYPE = os.getenv("MODAL_GPU_TYPE", "A10G")
GPU_TIMEOUT_S = int(os.getenv("MODAL_GPU_TIMEOUT_S", "3600"))
SPLAT_TIMEOUT_S = int(os.getenv("MODAL_SPLAT_TIMEOUT_S", "5400"))

# Late dependency management
try:
    from gpu_pipeline import GPUPipeline
    from storage.factory import get_storage_provider
except ImportError:
    from modal_worker.gpu_pipeline import GPUPipeline
    from storage.factory import get_storage_provider

def run_stage(job_id: str, stage_name: str, robust: bool = True):
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace_path = Path(temp_dir)
        storage = get_storage_provider()
        
        logger.info(f"🚀 GPU Stage {stage_name} Started: {job_id}")
        pipeline = GPUPipeline(workspace_path, storage, job_id)
        
        try:
            # 1. Pull data needed for this stage
            pipeline.pull_input(stage_name)
            
            # 2. Run logic
            telemetry = {}
            if stage_name == "SFM":
                telemetry = pipeline.run_sfm(robust=robust)
            elif stage_name == "MVS":
                telemetry = pipeline.run_mvs()
            elif stage_name == "MESH":
                telemetry = pipeline.run_mesh()
            elif stage_name == "SPLAT":
                telemetry = pipeline.run_splat()
            
            # 3. Push results back
            results = pipeline.push_output(stage_name)
            
            # Merge telemetry into results
            if isinstance(telemetry, dict):
                results.update(telemetry)
            
            return {"job_id": job_id, "status": "completed", "results": results}
        except Exception as e:
            logger.error(f"❌ GPU Stage {stage_name} Error: {str(e)}")
            return {"job_id": job_id, "status": "failed", "error": str(e)}

@app.function(image=image, gpu=GPU_TYPE, timeout=GPU_TIMEOUT_S, volumes={"/mnt/storage": volume}, secrets=[secret])
def run_sfm(job_id: str, robust: bool = True):
    return run_stage(job_id, "SFM", robust)

@app.function(image=image, gpu=GPU_TYPE, timeout=GPU_TIMEOUT_S, volumes={"/mnt/storage": volume}, secrets=[secret])
def run_mvs(job_id: str):
    return run_stage(job_id, "MVS")

@app.function(image=image, gpu=GPU_TYPE, timeout=GPU_TIMEOUT_S, volumes={"/mnt/storage": volume}, secrets=[secret])
def run_mesh(job_id: str):
    return run_stage(job_id, "MESH")

@app.function(image=image, gpu=GPU_TYPE, timeout=SPLAT_TIMEOUT_S, volumes={"/mnt/storage": volume}, secrets=[secret])
def run_splat(job_id: str):
    return run_stage(job_id, "SPLAT")

@app.function(image=image, volumes={"/mnt/storage": volume}, secrets=[secret])
def cleanup_job(job_id: str):
    storage = get_storage_provider()
    # We use a temporary workspace to instantiate the pipeline and call cleanup
    with tempfile.TemporaryDirectory() as temp_dir:
        pipeline = GPUPipeline(Path(temp_dir), storage, job_id)
        return pipeline.cleanup()