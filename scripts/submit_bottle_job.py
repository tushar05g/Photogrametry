import os
import requests
import glob

# Configuration
API_URL = "http://localhost:8000/scans/upload"
IMAGES_DIR = "/home/harpreet/Documents/3d_scanner/assets/images bottlr "

def submit_job():
    print(f"🚀 Collecting images from {IMAGES_DIR}...")
    
    # Get all png and jpg images
    image_paths = glob.glob(os.path.join(IMAGES_DIR, "*.png")) + glob.glob(os.path.join(IMAGES_DIR, "*.jpg"))
    
    if not image_paths:
        print("❌ No images found in the directory!")
        return

    print(f"📸 Found {len(image_paths)} images. Uploading...")

    # Prepare files for multipart upload
    files = []
    for path in sorted(image_paths):
        files.append(('files', (os.path.basename(path), open(path, 'rb'), 'image/png')))

    try:
        response = requests.post(API_URL, files=files)
        response.raise_for_status()
        
        data = response.json()
        job_id = data.get("job_id")
        print(f"✅ Job submitted successfully!")
        print(f"🆔 Job ID: {job_id}")
        print(f"ℹ️ Message: {data.get('message')}")
        
    except Exception as e:
        print(f"❌ Failed to submit job: {e}")
    finally:
        # Close all file handles
        for f in files:
            f[1][1].close()

if __name__ == "__main__":
    submit_job()
