import requests
import time
import os
import glob
from pathlib import Path

BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"

# Get project root directory (parent of 'tests' directory)
PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets" / "cube_images"

def test_pipeline_e2e():
    print("🚀 Starting E2E Pipeline Test")
    
    # 1. Prepare images
    image_files = list(ASSETS_DIR.glob("*.png"))
    print(f"📁 Looking for images in: {ASSETS_DIR}")
    print(f"📁 Found {len(image_files)} images")
    
    if not image_files:
        print("❌ No images found. Make sure assets/cube_images/ contains PNG files.")
        print(f"   Expected path: {ASSETS_DIR}")
        return

    # 2. Upload images
    print("📤 Uploading images...")
    files = [("files", (img.name, open(img, "rb"), "image/png")) for img in image_files]
    
    response = requests.post(f"{API_V1}/jobs/upload", files=files)
    if response.status_code != 200:
        print(f"❌ Upload failed: {response.text}")
        return
    
    job_data = response.json()
    job_id = job_data["job_id"]
    print(f"✅ Job created: {job_id}")

    # 3. Monitor status
    print("⏳ Monitoring job status...")
    start_time = time.time()
    last_stage = ""
    
    while True:
        try:
            status_response = requests.get(f"{API_V1}/scans/{job_id}/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data["status"]
                stage = status_data.get("current_stage") or status_data.get("stage", "PENDING")
                message = status_data.get("message", "")
                
                if stage != last_stage:
                    print(f"📍 Stage: {stage} - {message}")
                    last_stage = stage
                
                if status == "COMPLETED":
                    print(f"🎉 Job completed successfully in {time.time() - start_time:.1f}s!")
                    break
                elif status == "FAILED":
                    print(f"❌ Job failed: {message}")
                    break
            else:
                print(f"⚠️ Status check failed: {status_response.status_code}")
        except Exception as e:
            print(f"⚠️ Error checking status: {e}")
            
        time.sleep(5)
        if time.time() - start_time > 7200: # 2 hour timeout
            print("❌ Test timed out after 2 hours")
            break

    # 4. Get results
    print("📊 Fetching results...")
    results_response = requests.get(f"{API_V1}/scans/{job_id}/results")
    if results_response.status_code == 200:
        results_data = results_response.json()
        print(f"✅ Model URL: {results_data.get('model_url')}")
        print(f"✅ SPLAT URL: {results_data.get('splat_url')}")
        print(f"✅ Results: {results_data.get('results')}")
    else:
        print(f"❌ Failed to fetch results: {results_response.text}")

if __name__ == "__main__":
    test_pipeline_e2e()
