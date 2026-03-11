# 🚀 Morphic 3D Scanner - Complete Setup Guide

## Step 1: Set Up Your Backend (Local)

```bash
# Navigate to your project
cd /home/harpreet/Documents/3d_scanner

# Copy environment file
cp .env.example .env

# Edit .env with your credentials:
# - Cloudinary cloud name, API key, secret
# - Database URL
# - Redis URL

# Start all services
docker compose up --build
```

## Step 2: Get Your Ngrok URL

1. Open http://localhost:4040 in your browser
2. Copy the public URL (e.g., `https://random-words.ngrok-free.dev`)
3. This is your **BACKEND_URL**

## Step 3: Prepare Kaggle Worker

Your `kaggle_worker.py` is now **self-contained** (no external pipeline imports needed).

### Option A: Upload to Kaggle Dataset (Recommended)

1. **Create a zip file:**
```bash
cd /home/harpreet/Documents/3d_scanner/scripts
zip -r morphic_worker.zip kaggle_worker.py
```

2. **Upload to Kaggle:**
   - Go to Kaggle → Your Datasets → New Dataset
   - Upload `morphic_worker.zip`
   - Make it public

### Option B: Direct Download (Simpler)

Just use the raw file URL from your GitHub repo.

## Step 4: Kaggle Notebook Setup

Create a new Kaggle Notebook with **GPU T4 x2** enabled, then run this cell:

```python
# === CONFIGURATION ===
BACKEND_URL = "https://your-ngrok-url.ngrok-free.dev"  # Replace with your ngrok URL
CLOUDINARY_CLOUD_NAME = "your-cloud-name"            # Replace with your Cloudinary name
CLOUDINARY_API_KEY = "your-api-key"                   # Replace with your Cloudinary key
CLOUDINARY_API_SECRET = "your-api-secret"             # Replace with your Cloudinary secret

# === DOWNLOAD WORKER ===
!wget -O kaggle_worker.py https://raw.githubusercontent.com/your-username/morphic-scanner/main/scripts/kaggle_worker.py

# === UPDATE CONFIGURATION ===
with open("kaggle_worker.py", "r") as f:
    content = f.read()

content = content.replace('BACKEND_URL  = "https://ollie-unfashionable-topographically.ngrok-free.dev"', f'BACKEND_URL  = "{BACKEND_URL}"')
content = content.replace('CLOUD_NAME  = os.getenv("CLOUDINARY_CLOUD_NAME")', f'CLOUD_NAME  = "{CLOUDINARY_CLOUD_NAME}"')
content = content.replace('API_KEY     = os.getenv("CLOUDINARY_API_KEY")', f'API_KEY     = "{CLOUDINARY_API_KEY}"')
content = content.replace('API_SECRET  = os.getenv("CLOUDINARY_API_SECRET")', f'API_SECRET  = "{CLOUDINARY_API_SECRET}"')

with open("kaggle_worker.py", "w") as f:
    f.write(content)

# === START WORKER ===
import sys
sys.path.append('/kaggle/working')
from kaggle_worker import start_worker
start_worker()
```

## Step 5: Test the System

1. **Check Backend:** Open your frontend (usually http://localhost:3000)
2. **Upload Images:** Upload some photos of an object
3. **Monitor Worker:** Watch the Kaggle notebook output
4. **Get Results:** The 3D model should appear in your frontend

## Step 6: Troubleshooting

### If Worker Fails to Start:
- Check that your ngrok URL is correct
- Verify Cloudinary credentials
- Make sure GPU is enabled in Kaggle

### If Import Errors Occur:
- The worker is now self-contained, so no import issues should occur
- If you see "No module named 'pipeline'", the fix has been applied

### If Jobs Don't Process:
- Check Redis is running in your backend
- Verify worker registration in backend logs
- Check network connectivity between Kaggle and your ngrok URL

## Step 7: Architecture Overview

```
[Your Browser] → [Frontend] → [Backend] → [Redis Queue] → [Kaggle Worker]
     ↓                                                           ↓
[View 3D Model] ← [Cloudinary] ← [Worker processes images → 3D model]
```

### What Happens:
1. **Frontend**: Upload images via web interface
2. **Backend**: Receives images, creates job in Redis queue
3. **Kaggle Worker**: Pulls job, runs Gaussian Splatting pipeline
4. **Pipeline**: Masking → COLMAP → Neural Training → Mesh → Upload
5. **Frontend**: Displays final 3D model

## Key Files:
- `kaggle_worker.py`: Self-contained worker (fixed version)
- `docker-compose.yml`: Backend services
- `.env`: Your credentials
- `frontend/`: Web interface

## Success Indicators:
✅ Backend running with ngrok URL  
✅ Kaggle worker shows "GPU available: Tesla T4"  
✅ Worker registers with backend  
✅ Jobs process and show progress percentages  
✅ 3D models appear in frontend  

Your system is now ready for distributed 3D scanning!
