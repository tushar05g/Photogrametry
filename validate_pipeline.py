print("DEBUG: Validation script starting...")
import requests
import os
import time
from pathlib import Path

# 🚀 Validation Script for Refactored Pipeline

BASE_URL = "http://localhost:8000/api/v1"
CUBE_IMAGES_DIR = Path(__file__).parent / "assets" / "cube_images"

def validate_pipeline():
    print("🎯 Starting Pipeline Validation...")
    
    if not CUBE_IMAGES_DIR.exists():
        print(f"❌ Assets dir not found: {CUBE_IMAGES_DIR}")
        return

    # 1. Upload Images
    print(f"📤 Uploading images from {CUBE_IMAGES_DIR}...")
    files = []
    for img_path in sorted(CUBE_IMAGES_DIR.glob("*.png")):
        files.append(("files", (img_path.name, open(img_path, "rb"), "image/png")))
    
    try:
        resp = requests.post(f"{BASE_URL}/jobs/upload", files=files)
        resp.raise_for_status()
        data = resp.json()
        job_id = data["job_id"]
        print(f"✅ Job initiated: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return

    # 2. Poll for Completion
    print(f"⏳ Polling for job {job_id} status...")
    max_retries = 30
    for i in range(max_retries):
        try:
            status_resp = requests.get(f"{BASE_URL}/scans/{job_id}/status")
            status_data = status_resp.json()
            status = status_data["status"]
            stage = status_data["current_stage"]
            
            print(f"   [{i}/{max_retries}] Job Status: {status} | Current Stage: {stage}")
            
            if status == "COMPLETED":
                print("🎉 Pipeline Validation Successful!")
                # Get results
                results_resp = requests.get(f"{BASE_URL}/scans/{job_id}/results")
                print(f"📦 Results: {results_resp.json()}")
                return
            elif status == "FAILED":
                print("❌ Pipeline Failed!")
                return
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            
        time.sleep(5)

    print("⚠️ Timeout reached while waiting for pipeline.")

if __name__ == "__main__":
    validate_pipeline()
