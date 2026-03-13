"""
╔══════════════════════════════════════════════════════════╗
║   MORPHIC GPU WORKER v4.0 — GAUSSIAN SPLATTING ENGINE   ║
║             For Kaggle GPU Notebooks (T4/P100)           ║
╚══════════════════════════════════════════════════════════╝

🎓 TEACHER'S NOTE — HOW THIS WORKER FITS IN THE ARCHITECTURE:
==============================================================

This is a DISTRIBUTED WORKER. It is a completely separate Python script that runs
inside a Kaggle Notebook with GPU access. Here is its position in the system:

  [User's Browser] → [FastAPI Backend] → [Redis Queue] → [THIS WORKER]
                                              ↑
                                     This worker POLLS the queue

HOW THE PIPELINE WORKS (Gaussian Splatting Edition):
====================================================

TRADITIONAL PHOTOGRAMMETRY (old approach):
  photos → COLMAP → sparse point cloud → .PLY file (basic dots)

GAUSSIAN SPLATTING (our new approach):
  photos → COLMAP → sparse point cloud → 3D Gaussian model → Dense Mesh → .GLB

WHAT ARE "3D GAUSSIANS"?
  Imagine placing millions of tiny transparent "soap bubbles" in 3D space.
  Each bubble has:
    - A 3D position (x, y, z)
    - A shape (stretched like an egg or round like a ball)
    - A color / transparency
    - A "view-dependent" RGB color (changes as you rotate the camera)

  Neural networks learn to place these gaussians EXACTLY where they need to be
  to reconstruct the scene. The result looks photorealistic — much better than
  a sparse point cloud.

TOOL CHAIN:
  1. COLMAP         → Estimates camera poses from images (Structure-from-Motion)
  2. Nerfstudio     → Trains 3D Gaussian Splatting model (splatfacto)
  3. PyMeshLab      → Converts the gaussian splats into a triangle mesh
  4. trimesh        → Exports the mesh as a .GLB file (for web browsers)
  5. Cloudinary     → Uploads file for the frontend to display

INSTALL INSTRUCTIONS FOR KAGGLE:
  Run pipeline/install.py ONCE before the main script.
"""

import os
import sys
import time
import shutil
import subprocess
import requests
import logging
import signal
from pathlib import Path

# Fix path to include the project root
ROOT_DIR = Path("/kaggle/working")
sys.path.append(str(ROOT_DIR))

# Import our new robust modules
try:
    from pipeline.install import verify_versions, install_core_deps
    from pipeline.run_gaussian import GSREngine
except ImportError:
    # If running locally for testing
    sys.path.append(os.getcwd())
    from pipeline.install import verify_versions, install_core_deps
    from pipeline.run_gaussian import GSREngine

# ─────────────────────────────────────────────────────────
# ⚙️ CONFIGURATION & LOGGING
# ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

BACKEND_URL  = os.getenv("BACKEND_URL", "https://ollie-unfashionable-topographically.ngrok-free.dev")
WORKER_ID    = os.getenv("WORKER_ID", "kaggle-gpu-v4")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))

# Cloudinary credentials
CLOUD_NAME  = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY     = os.getenv("CLOUDINARY_API_KEY")
API_SECRET  = os.getenv("CLOUDINARY_API_SECRET")

# ─────────────────────────────────────────────────────────
# 🛰️ SYSTEM HEALTH & REGISTRATION
# ─────────────────────────────────────────────────────────

def check_environment():
    """
    🎓 TEACHER'S NOTE: Dependency Management.
    We verify package versions before importing them to prevent locking memory.
    If versions are incorrect, we run an atomic install script.
    """
    logger.info("📡 Checking environment...")
    
    if not verify_versions():
        logger.info("⚙️ Dependencies out of sync. Running atomic install...")
        install_core_deps()
    else:
        logger.info("✅ Core dependency versions verified.")

    # Ensure COLMAP is installed
    if shutil.which("colmap") is None:
        logger.info("⚙️ Installing COLMAP via APT...")
        subprocess.run(["apt-get", "update", "-qq"], check=True)
        subprocess.run(["apt-get", "install", "-y", "-qq", "colmap", "xvfb", "libgl1"], check=True)

def report_progress(job_id, status, progress=None, model_url=None, error_message=None):
    """Update backend on job state."""
    payload = {"status": status}
    if progress: payload["progress"] = progress
    if model_url: payload["model_url"] = model_url
    if error_message: payload["error_message"] = error_message
    
    try:
        requests.patch(f"{BACKEND_URL}/scans/{job_id}", json=payload, timeout=10)
    except Exception as e:
        logger.warning(f"⚠️ Failed to report progress: {e}")

# ─────────────────────────────────────────────────────────
# 🔥 MAIN JOB PROCESSOR
# ─────────────────────────────────────────────────────────

def process_job(job_data):
    """
    🎓 TEACHER'S NOTE: The Pipeline Controller.
    Instead of one big block, we delegate to specialized modules.
    We use the GSREngine to handle the complexity of SfM and Splatting.
    """
    job_id = job_data["job_id"]
    images = job_data.get("images", [])
    workspace = ROOT_DIR / f"job_{job_id[:8]}"
    
    if workspace.exists(): shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    images_dir = workspace / "images"
    images_dir.mkdir()

    logger.info(f"🚀 Starting job {job_id} with {len(images)} images")
    report_progress(job_id, "processing", "10% - Downloading images")

    # 1. Download images
    def is_job_cancelled():
        try:
            resp = requests.get(f"{BACKEND_URL}/scans/{job_id}", timeout=5)
            if resp.status_code == 200:
                return resp.json().get("status") == "cancelled"
        except: return False
        return False

    try:
        for i, url in enumerate(images):
            if i % 5 == 0 and is_job_cancelled():
                raise RuntimeError("Job cancelled by user.")
                
            img_data = requests.get(url, timeout=30).content
            with open(images_dir / f"img_{i:04d}.jpg", "wb") as f:
                f.write(img_data)
        
        # 2. Run Reconstruction Pipeline
        report_progress(job_id, "processing", "30% - Running reconstruction pipeline")
        
        # 🎓 TEACHER'S NOTE: The engine manages the full fallback chain:
        # Primary:   Nerfstudio splatfacto
        # Fallback1: Original Gaussian Splatting repo
        # Fallback2: COLMAP sparse export
        engine = GSREngine(str(workspace), cancel_check_func=is_job_cancelled)
        artifact_path = engine.run()
        
        # 3. Upload to Cloudinary
        report_progress(job_id, "processing", "90% - Uploading 3D model")
        
        from pipeline.step_upload import UploadStep
        uploader = UploadStep()
        model_url = uploader.execute(artifact_path, CLOUD_NAME, API_KEY, API_SECRET)

        report_progress(job_id, "completed", "100% - Ready!", model_url=model_url)
        logger.info(f"✅ Job {job_id} COMPLETED. URL: {model_url}")

    except Exception as e:
        logger.error(f"🚨 Job {job_id} FAILED: {str(e)}")
        report_progress(job_id, "failed", error_message=str(e)[:1000])
    finally:
        # Cleanup
        if workspace.exists(): shutil.rmtree(workspace)

# ─────────────────────────────────────────────────────────
# 🔄 WORKER LOOP
# ─────────────────────────────────────────────────────────

def start_worker():
    """
    🎓 TEACHER'S NOTE: The main worker loop.
    This worker runs CONTINUOUSLY and processes jobs from the backend.
    """
    check_environment()
    
    # Register
    try:
        requests.post(f"{BACKEND_URL}/workers/register", json={
            "worker_id": WORKER_ID,
            "url": "pull-mode"
        }, timeout=10)
    except: pass

    logger.info(f"🐝 Worker {WORKER_ID} listening for jobs...")
    
    while True:
        try:
            resp = requests.get(f"{BACKEND_URL}/workers/next-job", params={"worker_id": WORKER_ID}, timeout=15)
            if resp.status_code == 200:
                job_data = resp.json()
                if job_data.get("job_id"):
                    process_job(job_data)
        except Exception as e:
            logger.error(f"Loop error: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    def handle_exit(sig, frame):
        logger.info("🛑 Termination signal received. Cleaning up...")
        sys.exit(0)
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    start_worker()
