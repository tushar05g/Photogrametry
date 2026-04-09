import requests
import os
import time
import sys
from pathlib import Path

# Config
BASE_URL = "http://localhost:8000/api/v1"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "cube_images"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

def test_cube_e2e():
    print(f"🚀 Starting End-to-End Cube Test")
    print(f"📂 Assets: {ASSETS_DIR}")
    print(f"📂 Output: {OUTPUT_DIR}")

    # 1. Check health
    try:
        resp = requests.get(f"http://localhost:8000/health")
        resp.raise_for_status()
        print(f"✅ Backend is online")
    except Exception as e:
        print(f"❌ Backend is offline: {e}")
        return

    # 2. Upload images
    if not ASSETS_DIR.exists():
        print(f"❌ Assets directory not found")
        return
    
    images = list(ASSETS_DIR.glob("*.png"))
    if not images:
        print(f"❌ No images found in {ASSETS_DIR}")
        return
    
    print(f"📤 Uploading {len(images)} images...")
    files = [("files", (img.name, open(img, "rb"), "image/png")) for img in images]
    
    try:
        resp = requests.post(f"{BASE_URL}/jobs/upload", data={"project_name": "Cube_E2E_Test", "enable_splat": "true"}, files=files)
        resp.raise_for_status()
        job_data = resp.json()
        job_id = job_data["job_id"]
        print(f"✅ Job initiated: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return

    # 3. Poll for completion
    print(f"⏳ Monitoring job {job_id}...")
    start_time = time.time()
    timeout = 3600 # 1 hour
    
    last_stage = None
    
    while time.time() - start_time < timeout:
        try:
            resp = requests.get(f"{BASE_URL}/scans/{job_id}/progress")
            resp.raise_for_status()
            status_data = resp.json()
            
            status = status_data["status"]
            stage = status_data["current_stage"]
            progress = status_data["progress"]
            
            if stage != last_stage:
                print(f"   [{int(time.time() - start_time)}s] Stage: {stage} | Progress: {progress}")
                last_stage = stage
            
            if status == "completed":
                print(f"🎉 Job COMPLETED in {int(time.time() - start_time)}s")
                model_url = status_data.get("model_url")
                if model_url:
                    download_result(job_id, model_url)
                else:
                    print(f"⚠️ No model URL found in results")
                return
            elif status == "failed":
                print(f"❌ Job FAILED: {status_data.get('error_message')}")
                return
            
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
        
        time.sleep(10)
    
    print(f"❌ Timeout reached")

def download_result(job_id, url):
    print(f"📥 Downloading result from {url}...")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        
        # Determine extension from URL or fallback
        ext = ".obj"
        if ".ply" in url.lower():
            ext = ".ply"
        elif ".glb" in url.lower():
            ext = ".glb"
        
        filename = f"{job_id}_result{ext}"
        filepath = OUTPUT_DIR / filename
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(resp.content)
        
        print(f"✅ Result saved to: {filepath}")
        print(f"📏 Size: {len(resp.content)} bytes")
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    test_cube_e2e()
