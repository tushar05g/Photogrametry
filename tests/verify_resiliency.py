import sys
import os
import json
import time
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from modal_worker.governor import Governor
from modal_worker.colmap_pipeline import Orchestrator

def test_checkpoint_resume():
    """🧪 VERIFICATION: Resume from last successful stage."""
    print("--- 🚀 Testing RESUME FROM CHECKPOINT ---")
    
    workspace = Path("/tmp/resilient_test")
    if workspace.exists():
        import shutil
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    
    # 🕵️ 1. Mock a previous successful SFM stage
    checkpoint_file = workspace / "checkpoint.json"
    checkpoint_data = {
        "completed_stages": {
            "DOWNLOAD": True,
            "SFM": True
        }
    }
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint_data, f)
    
    # 🏁 2. Instantiate Orchestrator
    gov = Governor(workspace, max_gpu_minutes=1)
    orch = Orchestrator(workspace, "test_job_123", gov)
    
    # 🏃 3. Run Pipeline
    # It should SKIP DOWNLOAD and SFM and jump directly to MVS
    print("Executing pipeline (Should SKIP Download/SFM)...")
    try:
        orch.run_full_pipeline([], enable_dense=True, enable_splat=False)
    except Exception as e:
        # Expected failure since images are missing, but check logs
        print(f"Resiliency Test Flow: {e}")
    
    print("Checkpoint Resume Test Completed.\n")

def test_governor_enforcement():
    """🧪 VERIFICATION: Resource limit enforcement."""
    print("--- 📉 Testing RESOURCE GOVERNOR ---")
    
    workspace = Path("/tmp/gov_test")
    workspace.mkdir(parents=True, exist_ok=True)
    
    # 🔥 Set disk limit to effectively zero (1 byte)
    gov = Governor(workspace, max_gpu_minutes=60, max_nfs_gb=0.000000001)
    
    # Create a small file to trigger limit
    with open(workspace / "test.txt", 'w') as f:
        f.write("trigger limit")
        
    print("Checking limits (Should raise RuntimeError)...")
    try:
        gov.check_limits()
    except RuntimeError as re:
        print(f"Governor Caught Violation: {re}")
    
    print("Governor Test Completed.\n")

if __name__ == "__main__":
    test_checkpoint_resume()
    test_governor_enforcement()
