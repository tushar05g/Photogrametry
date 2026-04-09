
import requests
import os
import time
import sys
from pathlib import Path

# Config
BASE_URL = "http://localhost:8000/api/v1"
ASSETS_DIR = Path(__file__).parent.parent / "assets" / "mouse_video_frames" / "cleaned"
OUTPUT_DIR = Path(__file__).parent.parent / "output" / "mouse"

def test_mouse_e2e():
    print(f"🚀 Starting End-to-End Mouse Test (Cleaned Dataset)")
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
        print(f"❌ Assets directory not found. Please run scripts/clean_mouse_dataset.py first.")
        return
    
    images = list(ASSETS_DIR.glob("*.png"))
    if not images:
        print(f"❌ No images found in {ASSETS_DIR}")
        return
    
    print(f"📤 Uploading {len(images)} cleaned images...")
    # Use a generator to avoid keeping all file descriptors open at once
    files = [("files", (img.name, open(img, "rb"), "image/png")) for img in images]
    
    try:
        # 🏁 v10.2.0: Higher quality request
        resp = requests.post(
            f"{BASE_URL}/jobs/upload", 
            data={
                "project_name": "Mouse_E2E_Cleaned", 
                "enable_splat": "true",
                "quality": "high"
            }, 
            files=files
        )
        resp.raise_for_status()
        job_data = resp.json()
        job_id = job_data["job_id"]
        print(f"✅ Job initiated: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return
    finally:
        # Close all files
        for name, info in files:
            info[1].close()

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
                
                # Also check for splat
                # We need to call the results endpoint to get all URLs
                try:
                    res_resp = requests.get(f"{BASE_URL}/scans/{job_id}/results")
                    res_data = res_resp.json()
                    splat_url = res_data.get("splat_url")
                    if splat_url:
                        download_result(job_id, splat_url, "splat")
                except: pass
                
                return
            elif status == "failed":
                # 🏁 v10.2.0: Get detailed error message
                error_msg = status_data.get('error_message')
                print(f"❌ Job FAILED: {error_msg}")
                return
            
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
        
        time.sleep(15)
    
    print(f"❌ Timeout reached")

def download_result(job_id, url, tag="model"):
    print(f"📥 Downloading {tag} from {url}...")
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        
        # Determine extension from URL or fallback
        ext = ".obj"
        if ".ply" in url.lower():
            ext = ".ply"
        elif ".glb" in url.lower():
            ext = ".glb"
        elif ".splat" in url.lower():
            ext = ".splat"
        
        filename = f"{job_id}_{tag}{ext}"
        filepath = OUTPUT_DIR / filename
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(resp.content)
        
        print(f"✅ {tag.capitalize()} saved to: {filepath}")
        print(f"📏 Size: {len(resp.content)} bytes")
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    test_mouse_e2e()
