
import requests
import os
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
WORKSPACE = Path("/home/harpreet/Documents/3d_scanner")
TURTLE_DIR = WORKSPACE / "assets" / "turtle_images"
VIDEO_DIR = WORKSPACE / "assets" / "mouse_videos"

def trigger_turtle_job():
    print("📦 Triggering Turtle Image Job...")
    images = list(TURTLE_DIR.glob("*.png"))
    if not images:
        print(f"❌ No turtle images found in {TURTLE_DIR}!")
        return None
    
    files = [("files", (img.name, open(img, "rb"), "image/png")) for img in images]
    try:
        resp = requests.post(
            f"{BASE_URL}/jobs/upload",
            data={"project_name": "Turtle_Test_Final", "quality": "high"},
            files=files
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        print(f"✅ Turtle Job ID: {job_id}")
        return job_id
    except Exception as e:
        print(f"❌ Turtle Job failed: {e}")
        return None
    finally:
        for _, info in files:
            info[1].close()

def trigger_video_job():
    print("📦 Triggering Mouse Video Job...")
    videos = list(VIDEO_DIR.glob("*.mp4"))
    if not videos:
        print(f"❌ No mouse videos found in {VIDEO_DIR}!")
        return None
    
    # Just use one video for simplicity
    video = videos[0]
    files = [("files", (video.name, open(video, "rb"), "video/mp4"))]
    try:
        resp = requests.post(
            f"{BASE_URL}/jobs/upload-video",
            data={"project_name": "Mouse_Video_Test"},
            files=files
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        print(f"✅ Video Job ID: {job_id}")
        return job_id
    except Exception as e:
        print(f"❌ Video Job failed: {e}")
        return None
    finally:
        for _, info in files:
            info[1].close()

if __name__ == "__main__":
    t_id = trigger_turtle_job()
    v_id = trigger_video_job()
    
    if t_id or v_id:
        print("\n🚀 Both jobs initiated! Monitor them at http://localhost:8000/api/v1/scans/<id>/progress")
        print(f"Turtle: {t_id}")
        print(f"Video:  {v_id}")
