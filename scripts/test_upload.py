import os
import requests
import time
import sys
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent.parent
IMAGE_DIR = PROJECT_ROOT / "assets" / "sample_images" / "cube"
API_URL = "http://localhost:8001/api/v1/images"
PROGRESS_URL = "http://localhost:8001/scans/{job_id}/progress"
PROJECT_NAME = "Cube Test Scan"

def test_3d_generation():
    """
    Test the 3D generation flow by uploading images and monitoring progress.
    """
    # 1. Collect images
    image_files = sorted([
        f for f in os.listdir(IMAGE_DIR) 
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])
    
    if not image_files:
        print(f"❌ No image files found in {IMAGE_DIR}")
        return

    print(f"📸 Found {len(image_files)} images for testing.")

    # 2. Prepare upload
    files = []
    for img_name in image_files:
        img_path = IMAGE_DIR / img_name
        files.append(('files', (img_name, open(img_path, 'rb'), 'image/png')))

    # 3. Upload images
    print(f"🚀 Uploading images to {API_URL}...")
    try:
        response = requests.post(
            API_URL, 
            files=files, 
            data={'project_name': PROJECT_NAME},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        job_id = data.get("job_id")
        print(f"✅ Upload successful! Job ID: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return
    finally:
        # Close file handles
        for _, file_info in files:
            file_info[1].close()

    # 4. Monitor progress
    print(f"📊 Monitoring progress for Job {job_id}...")
    while True:
        try:
            status_resp = requests.get(PROGRESS_URL.format(job_id=job_id), timeout=10)
            status_resp.raise_for_status()
            status_data = status_resp.json()
            
            status = status_data.get("status")
            progress = status_data.get("progress", 0)
            message = status_data.get("message", "")
            
            print(f"   - Status: {status} | Progress: {progress}% | {message}")
            
            if status == "completed":
                print(f"🎉 3D Model Generation Completed successfully!")
                print(f"🔗 Model URL: {status_data.get('model_url')}")
                break
            elif status == "failed":
                print(f"❌ Job failed: {status_data.get('error_message')}")
                break
            elif status == "cancelled":
                print(f"⚠️ Job was cancelled.")
                break
            
            time.sleep(5)
        except Exception as e:
            print(f"⚠️ Error checking status: {e}")
            time.sleep(5)

if __name__ == "__main__":
    test_3d_generation()
