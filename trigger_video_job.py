import os
import requests
from pathlib import Path

# Base URL of the API
API_BASE = "http://localhost:8000/api/v1"

# Target Webhook
WEBHOOK_URL = "https://webhook.site/placeholder-v11-test"

def get_videos():
    video_dir = Path("./assets/mouse_videos")
    return list(video_dir.glob("*.mp4"))

def trigger():
    videos = get_videos()
    print(f"🚀 Found {len(videos)} videos in {Path('./assets/mouse_videos').absolute()}")
    
    if not videos:
        print("❌ No videos found!")
        return None

    print(f"📦 Uploading for Mouse video reconstruction...")
    
    # Prepare files and form data
    files = [('files', (vid.name, open(vid, 'rb'), 'video/mp4')) for vid in videos]
    data = {
        "project_name": "Mouse Video Reconstruction (Phase 1 Baseline)",
        "enable_splat": "true",
        "webhook_url": WEBHOOK_URL
    }
    
    try:
        resp = requests.post(f"{API_BASE}/jobs/upload-video", files=files, data=data)
        if resp.status_code == 200:
            job_data = resp.json()
            print(f"✅ Job initiated successfully!")
            print(f"🆔 Job ID: {job_data['job_id']}")
            print(f"🌐 Webhook: {job_data.get('webhook_url')}")
            print(f"🔗 Progress: {API_BASE}/scans/{job_data['job_id']}/progress")
            return job_data['job_id']
        else:
            print(f"❌ Failed to create job (Status {resp.status_code}): {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        return None

if __name__ == "__main__":
    trigger()
