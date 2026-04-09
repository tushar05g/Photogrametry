import os
import requests
import time
from pathlib import Path

# 🏁 v10.1.0: Updated Test Script for Unified Routing
BACKEND_URL = "http://localhost:8000"
PROJECT_NAME = "Cube Automated Test"
IMAGE_DIR = "assets/cube_images"

def test_reconstruction():
    print(f"🚀 Starting automated test for project: {PROJECT_NAME}")
    
    # 1. Collect images
    image_paths = sorted(list(Path(IMAGE_DIR).glob("*.png")))
    if not image_paths:
        print(f"❌ No images found in {IMAGE_DIR}")
        return
    print(f"📂 Found {len(image_paths)} images in {IMAGE_DIR}")
    
    # 2. Upload images
    print("📤 Uploading images to backend...")
    files = []
    for p in image_paths:
        files.append(('files', (p.name, open(p, 'rb'), 'image/png')))
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/jobs/upload",
            data={"project_name": PROJECT_NAME},
            files=files
        )
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f"✅ Upload successful! Job ID: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return

    # 3. Poll for progress
    print(f"📡 Monitoring job {job_id}...")
    # We try different polling endpoints to verify unified routing
    polling_endpoints = [
        f"/api/v1/scans/{job_id}/progress",
        f"/api/v1/job/{job_id}/progress",
        f"/scans/{job_id}/progress"
    ]
    
    endpoint_idx = 0
    last_stage = None
    
    while True:
        try:
            url = f"{BACKEND_URL}{polling_endpoints[endpoint_idx % len(polling_endpoints)]}"
            res = requests.get(url)
            res.raise_for_status()
            status = res.json()
            
            curr_status = status.get("status")
            curr_stage = status.get("current_stage")
            progress = status.get("progress")
            warning = status.get("warnings")
            
            if curr_stage != last_stage or warning:
                print(f"🔄 [{time.strftime('%H:%M:%S')}] Stage: {curr_stage} | Progress: {progress}")
                if warning:
                    print(f"   ⚠️ Warning: {warning}")
                last_stage = curr_stage
            
            if curr_status == "completed":
                print(f"✅ Job Completed Successfully!")
                print(f"🔗 Model URL: {status.get('model_url')}")
                break
            elif curr_status == "failed":
                print(f"❌ Job Failed: {status.get('error_message')}")
                break
            
            endpoint_idx += 1 # Cycle through endpoints
            time.sleep(10)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    test_reconstruction()
