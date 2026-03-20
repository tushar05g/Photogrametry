"""
╔══════════════════════════════════════════════════════════╗
║   MORPHIC GPU WORKER v4.0 — CLEAN RESTART            ║
║  Simple, reliable 3D reconstruction pipeline            ║
╚════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import shutil
import subprocess
import requests
import logging
import signal

# Configuration
BACKEND_URL = "https://ollie-unfashionable-topographically.ngrok-free.dev"
WORKER_ID = f"kaggle-gpu-{int(time.time())}"
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "your-cloud-name")
API_KEY = os.getenv("CLOUDINARY_API_KEY", "your-api-key")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "your-api-secret")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def install_dependencies():
    """Install required packages."""
    logger.info("Installing dependencies...")
    
    # System packages
    subprocess.run(["apt-get", "update", "-qq"], capture_output=True)
    subprocess.run([
        "apt-get", "install", "-y", "-qq",
        "colmap", "xvfb", "libgl1", "libglvnd0", "libglx0", "libglew2.2", "git"
    ], capture_output=True)
    
    # Python packages
    subprocess.run([
        "pip", "install", "-q",
        "numpy", "opencv-python-headless", "trimesh", "pymeshlab",
        "cloudinary", "requests", "nerfstudio", "torch", "torchvision",
        "Pillow", "matplotlib", "tqdm"
    ], capture_output=True)
    
    logger.info("Dependencies installed successfully")

def process_job(job_data):
    """Process a 3D reconstruction job."""
    job_id = job_data.get("job_id", "unknown")
    images = job_data.get("images", [])
    workspace = f"/kaggle/working/job_{job_id[:8]}"
    
    logger.info(f"Starting job {job_id} with {len(images)} images")
    
    try:
        os.makedirs(workspace, exist_ok=True)
        
        # Import pipeline steps
        from pipeline.step_masking import MaskingStep
        from pipeline.step_colmap import ColmapStep
        from pipeline.step_splatting import SplattingStep
        from pipeline.step_meshing import MeshingStep
        from pipeline.step_upload import UploadStep
        
        # Initialize steps
        masking = MaskingStep()
        colmap = ColmapStep()
        splatting = SplattingStep()
        meshing = MeshingStep()
        upload = UploadStep()
        
        # Step 1: Download images
        logger.info("Step 1/5: Downloading images...")
        images_dir = os.path.join(workspace, "images")
        masking.execute(images, images_dir)
        
        # Step 2: COLMAP reconstruction
        logger.info("Step 2/5: Running COLMAP...")
        undistorted_dir = colmap.execute(images_dir, workspace)
        
        # Step 3: Gaussian Splatting
        logger.info("Step 3/5: Running Gaussian Splatting...")
        ply_path = splatting.execute(workspace, data_dir=undistorted_dir)
        
        if not ply_path:
            raise RuntimeError("Gaussian Splatting failed")
        
        # Step 4: Mesh generation
        logger.info("Step 4/5: Creating mesh...")
        glb_path = meshing.execute(ply_path, workspace)
        
        if not glb_path:
            raise RuntimeError("Mesh generation failed")
        
        # Step 5: Upload
        logger.info("Step 5/5: Uploading model...")
        model_url = upload.execute(glb_path)
        
        # Cleanup
        shutil.rmtree(workspace, ignore_errors=True)
        
        logger.info(f"Job {job_id} completed successfully")
        return {
            "job_id": job_id,
            "status": "completed",
            "model_url": model_url,
            "worker_id": WORKER_ID
        }
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        shutil.rmtree(workspace, ignore_errors=True)
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
            "worker_id": WORKER_ID
        }

def get_next_job():
    """Get next job from backend."""
    try:
        resp = requests.get(f"{BACKEND_URL}/workers/next-job",
                          params={"worker_id": WORKER_ID},
                          timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("job_id"):
                return data
    except:
        pass
    return None

def report_progress(job_id, **fields):
    """Send progress update to backend."""
    try:
        requests.patch(f"{BACKEND_URL}/scans/{job_id}",
                      json=fields, timeout=10)
    except Exception as e:
        logger.warning(f"Failed to report progress: {e}")

def start_worker():
    """Main worker loop with graceful shutdown."""
    install_dependencies()
    
    logger.info("╔" + "═" * 60 + "╗")
    logger.info("║  MORPHIC GPU WORKER v4.5 — SENIOR STABILIZED   ║")
    logger.info("║  Robust COLMAP + Visible Progress Bars         ║")
    logger.info("╚" + "═" * 60 + "╝")
    logger.info(f"Backend: {BACKEND_URL}")
    logger.info(f"Worker ID: {WORKER_ID}")
    
    # Graceful shutdown handler
    def shutdown_handler(signum, frame):
        logger.info(f"Received signal {signum}. Cleaning up...")
        try:
            requests.post(f"{BACKEND_URL}/workers/{WORKER_ID}/idle", timeout=5)
        except:
            pass
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Register worker
    try:
        requests.post(f"{BACKEND_URL}/workers/register", json={
            "worker_id": WORKER_ID,
            "worker_type": "gpu",
            "capabilities": ["colmap", "gaussian-splatting", "meshing"]
        }, timeout=10)
        logger.info("Worker registered successfully. Status: Listening for jobs...")
    except Exception as e:
        logger.warning(f"Registration failed: {e}")
    
    # Main loop
    while True:
        try:
            job_data = get_next_job()
            if job_data and job_data.get("job_id"):
                job_id = job_data["job_id"]
                logger.info(f"Picked up job: {job_id}")
                
                # Immediate status sync for frontend
                report_progress(job_id, status="processing", progress="5% - Initializing workspace...")
                
                result = process_job(job_data)
                
                # Report result
                if result["status"] == "completed":
                    report_progress(job_id,
                                  status="completed",
                                  model_url=result["model_url"],
                                  progress="100% - Finished!")
                else:
                    report_progress(job_id,
                                  status="failed",
                                  error_message=result["error"])
                
                # Mark worker idle after job
                requests.post(f"{BACKEND_URL}/workers/{WORKER_ID}/idle", timeout=10)
            else:
                # No job, quick status check to keep ngrok tunnel alive if needed
                time.sleep(10)
                
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    start_worker()
