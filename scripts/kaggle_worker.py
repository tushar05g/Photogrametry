import os
import time
import requests
import logging
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("worker.log")
    ]
)
logger = logging.getLogger("kaggle_worker")

def check_dependencies():
    """Verify that required binaries are available."""
    try:
        subprocess.run(["colmap", "help"], capture_output=True, check=False)
        logger.info("✅ COLMAP found")
    except FileNotFoundError:
        logger.warning("⚠️ COLMAP not found in PATH! SFM will fail.")
        logger.warning("Run: !apt-get update && apt-get install -y colmap")

try:
    from modal_worker.gpu_pipeline import GPUPipeline
    from storage.factory import get_storage_provider
    from shared.schemas import JobStatus, JobStage, StageStatus
except ImportError as e:
    logger.error(f"❌ Missing local modules: {e}")
    logger.error("Ensure you've uploaded 'modal_worker/', 'storage/', and 'shared/' directories to the workspace.")
    sys.exit(1)

class KaggleWorker:
    def __init__(self, backend_url: str, worker_token: str):
        self.backend_url = backend_url.rstrip("/")
        self.worker_token = worker_token
        
        # Detection for Kaggle/Colab
        if os.path.exists("/kaggle/working"):
            self.env_type = "Kaggle"
            self.base_workspace = Path("/kaggle/working/photogrammetry")
        elif os.path.exists("/content"):
            self.env_type = "Colab"
            self.base_workspace = Path("/content/photogrammetry")
        else:
            self.env_type = "Standalone"
            self.base_workspace = Path("/tmp/photogrammetry_workspace")
            
        self.worker_id = f"{self.env_type.lower()}-{os.getenv('HOSTNAME', 'worker')}"
        self.storage = get_storage_provider()
        
        self.base_workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"📍 Workspace initialized at: {self.base_workspace}")

    @property
    def headers(self):
        return {"X-Worker-Token": self.worker_token}

    def poll(self) -> Optional[Dict[str, Any]]:
        """Poll the backend for pending GPU jobs."""
        try:
            url = f"{self.backend_url}/api/v1/worker/poll"
            response = requests.post(
                url, 
                params={"worker_id": self.worker_id},
                headers=self.headers,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("job_id"):
                    return data
            return None
        except Exception as e:
            logger.error(f"📡 Polling error: {e}")
            return None

    def update_stage(self, job_id: str, stage: JobStage, status: StageStatus, results: Optional[Dict] = None, error: Optional[str] = None):
        """Report progress back to backend."""
        try:
            url = f"{self.backend_url}/api/v1/worker/{job_id}/stage"
            payload = {
                "stage_name": stage,
                "status": status,
                "error_message": error,
                "results": results
            }
            requests.post(url, json=payload, headers=self.headers, timeout=10)
        except Exception as e:
            logger.error(f"⚠️ Status update error: {e}")

    def run_job(self, job_data: Dict[str, Any]):
        job_id = job_data["job_id"]
        logger.info(f"🚀 [Job {job_id}] Acquired! Environment: {self.env_type}")

        try:
            # 1. Initialize Pipeline with worker's workspace
            pipeline = GPUPipeline(self.base_workspace / job_id, self.storage, job_id)
            
            # 2. SFM
            self.update_stage(job_id, JobStage.SFM, StageStatus.IN_PROGRESS)
            pipeline.pull_input("SFM")
            sfm_res = pipeline.run_sfm()
            if sfm_res.get("status") == "failed":
                self.update_stage(job_id, JobStage.SFM, StageStatus.FAILED, error=sfm_res.get("error"))
                return
            sfm_outputs = pipeline.push_output("SFM")
            
            # 3. MVS
            self.update_stage(job_id, JobStage.MVS, StageStatus.IN_PROGRESS)
            mvs_res = pipeline.run_mvs()
            mvs_outputs = pipeline.push_output("MVS")
            
            # 4. MESH
            self.update_stage(job_id, JobStage.MESH, StageStatus.IN_PROGRESS)
            mesh_res = pipeline.run_mesh()
            mesh_outputs = pipeline.push_output("MESH")
            
            # 5. Complete
            final_results = {
                "mesh": mesh_outputs.get("mesh"),
                "mesh_glb": mesh_outputs.get("mesh_glb"),
                "sparse_pcd": sfm_outputs.get("sparse_pcd"),
                "dense_pcd": mvs_outputs.get("dense_pcd"),
                "point_count": mesh_outputs.get("point_count") or mvs_outputs.get("point_count") or sfm_res.get("point_count", 0),
                "worker_id": self.worker_id,
                "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            
            url = f"{self.backend_url}/api/v1/worker/{job_id}/complete"
            requests.post(url, json=final_results, headers=self.headers, timeout=10)
            logger.info(f"✅ [Job {job_id}] Pipeline completed successfully!")

        except Exception as e:
            logger.error(f"❌ [Job {job_id}] Critical failure: {e}", exc_info=True)
            self.update_stage(job_id, JobStage.SFM, StageStatus.FAILED, error=f"Worker Crash: {str(e)}")

    def start(self):
        check_dependencies()
        logger.info(f"🤖 Worker [{self.worker_id}] ready. Polling {self.backend_url} every 15s...")
        try:
            while True:
                job = self.poll()
                if job:
                    self.run_job(job)
                else:
                    time.sleep(15)
        except KeyboardInterrupt:
            logger.info("👋 Worker shutting down gracefully...")

if __name__ == "__main__":
    # Load settings from environment
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    WORKER_TOKEN = os.getenv("WORKER_TOKEN", "test-token-123")
    
    if not BACKEND_URL.startswith("http"):
        logger.error("❌ Invalid BACKEND_URL. Must start with http:// or https://")
        sys.exit(1)
        
    worker = KaggleWorker(BACKEND_URL, WORKER_TOKEN)
    worker.start()
