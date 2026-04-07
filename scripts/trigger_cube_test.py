import requests
import os
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1/jobs"
IMAGE_DIR = "assets/cube_images"

def trigger():
    images = [f for f in os.listdir(IMAGE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    print(f"Found {len(images)} images. Uploading...")
    
    files = []
    for img in images:
        files.append(('files', open(os.path.join(IMAGE_DIR, img), 'rb')))
    
    # Using the /upload endpoint which handles multi-part upload and starts the job
    resp = requests.post(f"{BASE_URL}/upload", params={"project_name": "Manual-Cube-Test"}, files=files)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Job started! Job ID: {data['job_id']}")
        return data['job_id']
    else:
        print(f"❌ Failed to start job: {resp.status_code} - {resp.text}")
        return None

if __name__ == "__main__":
    trigger()
