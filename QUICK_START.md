# 🐢 Local 3D Model Generation Scripts

Three scripts to test the photogrammetry pipeline locally:

## Quick Comparison

| Script | Purpose | Runtime | Use Case |
|--------|---------|---------|----------|
| **start_and_test.py** | ⭐ Recommended | ~10 min | Full automated test (start backend + generate models) |
| **start_backend.py** | Manual testing | ∞ (runs continuously) | Start backend only for manual API testing |
| **test_local_3d_generation.py** | Manual testing | ~5-10 min | Run tests against already-running backend |

## 🎯 How to Use

### Option 1️⃣: Automated (Easiest) ⭐ **RECOMMENDED**

```bash
# One command does everything:
python start_and_test.py
```

**What happens:**
1. ✅ Starts backend server
2. ✅ Waits for it to be ready
3. ✅ Uploads turtle images (17 files) → creates 3D model
4. ✅ Monitors progress through all stages
5. ✅ Downloads PLY/OBJ model files
6. ✅ Repeats for cube images (18 files)
7. ✅ Shuts down backend cleanly
8. ✅ Shows summary with model locations

**Output files saved to:**
```
output/3d_models/
├── job_id_1_ply.ply       (Turtle model)
├── job_id_2_ply.ply       (Cube model)
└── ...
```

### Option 2️⃣: Manual Backend + Automatic Tests

**Terminal 1 (Backend):**
```bash
python start_backend.py
```

Wait until you see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

**Terminal 2 (Tests):**
```bash
python test_local_3d_generation.py
```

### Option 3️⃣: Full Manual Control

**Terminal 1 (Backend):**
```bash
# Activate venv first
.\venv\Scripts\activate.bat

# Start backend
python -m uvicorn backend.main:app --reload
```

**Terminal 2 (Manual Testing):**
```bash
# Try API endpoints manually
curl http://localhost:8000/health

# Upload images and get job ID manually via REST API
# ... (use Postman, curl, or Python requests)
```

## 🔧 Script Details

### start_and_test.py

**Features:**
- Auto-starts backend server
- Waits for backend to be ready before testing
- Uploads both turtle and cube images
- Monitors progress with real-time status updates
- Downloads generated models automatically
- Shuts down backend cleanly on completion or error
- Handles timeouts gracefully

**Dependencies:**
- requests library (included in venv)
- Working backend code
- Turtle and cube image assets

**Error Handling:**
- Verifies project structure before starting
- Checks venv is properly configured
- Validates asset files exist
- Confirms backend startup
- Detects network/timeout errors

### start_backend.py

**Features:**
- Starts FastAPI backend in development mode with auto-reload
- Shows startup logs in terminal
- Runs until you press Ctrl+C
- Useful for API development or manual testing

**Access:**
- Health check: http://localhost:8000/health
- API docs: http://localhost:8000/docs (Swagger UI)
- API docs: http://localhost:8000/redoc (ReDoc)

### test_local_3d_generation.py

**Features:**
- Connects to running backend
- Uploads image sets
- Monitors job progress
- Downloads completed models
- Can be run multiple times (for different image sets)

**Customization:**
Edit these lines to customize:

```python
# Change backend URL (default: http://localhost:8000)
BASE_URL = "http://localhost:8000"

# Change output directory
OUTPUT_DIR = PROJECT_ROOT / "output" / "3d_models"

# Enable/disable splat file generation
enable_splat=False  # Change to True for splat files
```

## 📊 Expected Output

### When Everything Works ✅

```
═══════════════════════════════════════════════════════════════════════════
🐢 LOCAL 3D MODEL GENERATION TEST 🐢
═══════════════════════════════════════════════════════════════════════════

✅ Backend is online

═══════════════════════════════════════════════════════════════════════════
🧪 Processing: Turtle_3D_Model
═══════════════════════════════════════════════════════════════════════════
📤 Uploading 17 images from turtle_images...
✅ Job created: turtle_job_12345
   Images: 17
   Project: Turtle_3D_Model

⏳ Monitoring job turtle_job_12345...
   [6s] PREPROCESS (15%)
   [15s] SFM (30%)
   [45s] MVS (60%)
   [95s] MESH (85%)
   [120s] EXPORT (100%)

🎉 Job completed successfully in 122s

📊 Results Summary:
   Job ID: turtle_job_12345
   Status: completed

📥 Downloading PLY model...
   Progress: 100%
✅ Downloaded: output/3d_models/turtle_job_12345_ply.ply

✅ Project complete: Turtle_3D_Model

🎉 ALL TESTS COMPLETED SUCCESSFULLY
```

## 🚨 Common Issues & Solutions

### Backend won't start
```bash
# Port 8000 might be in use
netstat -ano | findstr :8000    # Find what's using it
```

### FileNotFoundError: No PNG images found
```bash
# Check assets exist
ls assets/turtle_images/    # Should show 17 .png files
ls assets/cube_images/      # Should show 18 .png files
```

### Connection refused to localhost:8000
```bash
# Backend not running or not started yet
# Make sure Terminal 1 shows "Application startup complete"
```

### Module not found errors
```bash
# Make sure you're in project root
pwd    # Should be .../photogrametry

# Verify venv is active
which python    # Should show venv path
```

## 📈 Performance Notes

### Typical Timing

| Stage | Duration |
|-------|----------|
| Upload 17 images | 10-30 sec |
| PREPROCESS | 10 sec |
| SFM (feature extraction) | 30-60 sec |
| MVS (dense reconstruction) | 60-120 sec |
| MESH generation | 30-60 sec |
| EXPORT to formats | 10 sec |
| **Total per image set** | **~3-5 min** |
| **Both turtle + cube** | **~5-10 min** |

### System Requirements

- **CPU:** 2+ cores recommended (can use 1, will be slower)
- **RAM:** 4 GB minimum (8+ GB recommended for large images)
- **Disk:** 2 GB free space
- **Network:** Stable connection to localhost

### Quality Tradeoffs

```python
# In test scripts, you can customize:

# Faster processing (lower quality)
enable_splat=False         # Skip splat generation

# Slower but better quality
enable_dense=True          # Full dense reconstruction
enable_splat=True          # Generate splat files
```

## ✅ Pre-flight Checklist

Before running scripts:

- [ ] venv created: `venv/` folder exists
- [ ] Dependencies installed: `pip list | grep fastapi` shows results
- [ ] Assets present: `assets/turtle_images/` (17 files) and `assets/cube_images/` (18 files)
- [ ] Backend code: `backend/main.py` exists
- [ ] Port 8000 free: `netstat -ano | findstr :8000` returns nothing
- [ ] Disk space: At least 2 GB free
- [ ] RAM available: At least 2-4 GB free

## 🎯 Next Steps

1. **Run the test:**
   ```bash
   python start_and_test.py
   ```

2. **Wait for completion** (~5-10 minutes)

3. **Check generated models:**
   ```bash
   ls output/3d_models/
   ```

4. **View models:**
   - Download free 3D viewer (Meshlab, 3D Viewer)
   - Or use online viewer (Sketchfab)
   - Open the .ply or .obj files

---

**Status:** ✅ **Ready to generate 3D models**

**Recommended command:** 
```bash
python start_and_test.py
```
