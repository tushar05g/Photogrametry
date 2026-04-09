import os
import requests
import time

API_URL = "http://localhost:8000/api/v1"
IMAGE_DIR = "assets/cube_images"
PROJECT_NAME = "Cube Automated Test"

def run_test():
    print(f"🚀 Starting automated test for project: {PROJECT_NAME}")
    
    # Get all images
    files = [f for f in os.listdir(IMAGE_DIR) if f.endswith(('.png', '.jpg', '.jpeg'))]
    files.sort()
    
    print(f"📂 Found {len(files)} images in {IMAGE_DIR}")
    
    # Prepare multipart form data
    upload_files = []
    for f in files:
        file_path = os.path.join(IMAGE_DIR, f)
        upload_files.append(('files', (f, open(file_path, 'rb'), 'image/png')))
    
    # Add form fields
    data = {
        'project_name': PROJECT_NAME,
        'enable_splat': 'true'
    }
    
    print("📤 Uploading images to backend...")
    try:
        response = requests.post(f"{API_URL}/jobs/upload", files=upload_files, data=data)
        response.raise_for_status()
        result = response.json()
        job_id = result.get('job_id')
        print(f"✅ Upload successful! Job ID: {job_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return

    # Monitor progress
    print(f"📡 Monitoring job {job_id}...")
    completed = False
    last_progress = ""
    
    while not completed:
        try:
            resp = requests.get(f"{API_URL}/scans/{job_id}/progress")
            resp.raise_for_status()
            status_data = resp.json()
            
            status = status_data.get('status')
            progress = status_data.get('progress')
            
            if progress != last_progress:
                print(f"⏳ [{time.strftime('%H:%M:%S')}] Status: {status.upper()} | Progress: {progress}")
                last_progress = progress
            
            if status == 'completed':
                print(f"🎉 Job COMPLETED! Model URL: {status_data.get('model_url')}")
                completed = True
            elif status == 'failed':
                print(f"❌ Job FAILED: {status_data.get('error_message')}")
                completed = True
            
            time.sleep(10)
        except Exception as e:
            print(f"⚠️ Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_test()
