import os
import requests
from pathlib import Path

# Base URL of the API
API_BASE = "http://localhost:8000/api/v1"

# Folder where artifacts are (locally)
# Since I'm the agent, I know they are in the current session's artifact folder
# but I'll just use the absolute paths I have.

images = [
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_front_view_1775710422388.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_45_right_1775710462830.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_45_left_1775710482840.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_90_right_1775710505553.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_90_left_1775710523247.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_135_right_1775711372159.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_135_left_1775711390260.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_back_1775711411108.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_top_1775711429478.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_high_front_1775711447299.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_90r_high_1775711640980.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_90l_high_1775711657787.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_135r_high_1775711677217.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_135l_high_1775711696709.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_180_high_1775711714573.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_front_low_1775711731737.png",
    "/home/harpreet/.gemini/antigravity/brain/a90151c1-0b58-4d9e-a947-de642c1d7eac/turtle_v1_90r_low_1775711752090.png"
]

def trigger():
    print(f"🚀 Uploading {len(images)} images for Turtle reconstruction...")
    files = [('files', (Path(img).name, open(img, 'rb'), 'image/png')) for img in images]
    
    resp = requests.post(f"{API_BASE}/jobs/upload", files=files)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ Job created: {data['job_id']}")
        return data['job_id']
    else:
        print(f"❌ Failed to create job: {resp.text}")
        return None

if __name__ == "__main__":
    trigger()
