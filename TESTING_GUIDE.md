# 🐢 Local 3D Model Generation - Test Guide

This guide explains how to run the local photogrammetry pipeline to generate 3D models from the turtle and cube image assets.

## 📋 Prerequisites

Before running the tests, ensure you have:

1. **Backend Requirements**
   - ✅ All 40 dependencies installed in venv
   - ✅ Backend code validated and tested (88.2% test success)
   - ✅ Project structure properly set up

2. **Asset Files**
   - ✅ Turtle images: `assets/turtle_images/` (17 PNG files)
   - ✅ Cube images: `assets/cube_images/` (18 PNG files)

3. **Database & Redis** (for full pipeline)
   - SQLite database (auto-created or use Neon PostgreSQL)
   - Redis server running (optional for basic testing, required for job queue)

## 🚀 Quick Start (Recommended)

**One-command test execution:**

```bash
python start_and_test.py
```

This script will:
1. ✅ Start the FastAPI backend server on `http://localhost:8000`
2. ✅ Wait for backend to be ready
3. ✅ Upload turtle images and create job
4. ✅ Monitor job progress through all stages
5. ✅ Download generated 3D models
6. ✅ Repeat for cube images
7. ✅ Shut down backend cleanly

## 🔧 Manual Step-by-Step (Advanced)

### Step 1: Start Backend Server

Open a terminal and run:

```bash
# Activate venv
.\venv\Scripts\activate.bat    # Windows
source venv/bin/activate       # Unix/Mac

# Start backend
python -m uvicorn backend.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Step 2: Verify Backend Health

Open another terminal and check:

```bash
# Windows
curl http://localhost:8000/health

# Unix/Mac
curl http://localhost:8000/health
```

Expected response: `{"status": "ok"}`

### Step 3: Run Model Generation Tests

In the second terminal, run:

```bash
# Activate venv
.\venv\Scripts\activate.bat    # Windows
source venv/bin/activate       # Unix/Mac

# Run tests
python test_local_3d_generation.py
```

## 📊 Pipeline Stages for Each Image Set

The pipeline processes images through these stages:

```
DOWNLOAD    → (Images already local, skipped)
PREPROCESS  → Scale, denoise, format image data
SFM         → Structure-from-Motion (COLMAP point cloud)
MVS         → Multi-View Stereo (dense point cloud)
MESH        → Mesh generation from point cloud
SPLAT       → Gaussian Splatting (optional)
EXPORT      → Save OBJ, PLY, GLB, SPLAT formats
```

**Expected Timeline:**
- Turtle (17 images): ~2-5 minutes
- Cube (18 images): ~2-5 minutes
- **Total with both: ~5-10 minutes**

## 📁 Output Files

Generated models are saved to:

```
output/
├── 3d_models/
│   ├── turtle/
│   │   ├── model.ply           # Point cloud
│   │   ├── model.obj           # Mesh
│   │   ├── model.glb           # Optimized mesh
│   │   └── model.splat         # Gaussian splat (if enabled)
│   └── cube/
│       ├── model.ply
│       ├── model.obj
│       └── model.glb
```

## 🔍 Understanding Test Output

### Example: Successful Test

```
✅ Backend is online
========================================
🧪 Processing: Turtle_3D_Model
========================================
📤 Uploading 17 images...
✅ Job created: turtle_job_123abc

⏳ Monitoring job turtle_job_123abc...
   [5s] PREPROCESS (10%)
   [12s] SFM (25%)
   [45s] MVS (50%)
   [120s] MESH (75%)
   [180s] EXPORT (100%)

🎉 Job completed successfully in 185s

📊 Results Summary:
   Job ID: turtle_job_123abc
   Status: completed

📥 Downloading PLY model...
   Progress: 100%
✅ Downloaded: output/3d_models/turtle_job_123abc_ply.ply

✅ Project complete: Turtle_3D_Model

========================================
📊 FINAL SUMMARY
========================================
✅ Completed 1 job(s):

   Project: Turtle_3D_Model
   Job ID: turtle_job_123abc
   Status: completed
   Models: output/3d_models/turtle_job_123abc
```

### What Each Stage Means

| Stage | Action | Time |
|-------|--------|------|
| **PREPROCESS** | Validate images, extract metadata | ~10 sec |
| **SFM** | Extract features, match between images | ~30-60 sec |
| **MVS** | Create dense point cloud | ~60-120 sec |
| **MESH** | Generate mesh surface | ~30-60 sec |
| **SPLAT** | Generate Gaussian splat (optional) | ~30 sec |
| **EXPORT** | Save to OBJ, PLY, GLB formats | ~10 sec |

## ⚙️ Configuration

### Key Settings (in `backend/config.py`):

```python
WORKER_STRATEGY = "pull"           # Use local worker
ENABLE_DENSE = True                # Full dense reconstruction
ENABLE_SPLAT = True                # Generate splat files
ENABLE_MESH = True                 # Generate mesh
STORAGE_TYPE = "local"             # Save to disk
DATABASE_URL = "sqlite://..."      # Use SQLite (local)
```

### Environment Variables

The test uses these defaults:

```
DATABASE_URL=sqlite:///./photogrammetry.db
REDIS_URL=redis://localhost:6379/0
WORKER_STRATEGY=pull
ENABLE_DENSE=true
ENABLE_SPLAT=false
STORAGE_TYPE=local
```

## 🐛 Troubleshooting

### ❌ "Backend offline"

**Problem:** Connection refused to http://localhost:8000

**Solutions:**
```bash
# Make sure backend is running in first terminal
# Check if another process is using port 8000
netstat -ano | findstr :8000    # Windows
lsof -i :8000                   # Unix/Mac

# Kill conflicting process if needed, then restart backend
```

### ❌ "No PNG images found"

**Problem:** Pipeline can't find turtle_images or cube_images

**Solutions:**
```bash
# Verify asset files exist
cd assets
ls -la turtle_images/    # Should show 17 .png files
ls -la cube_images/      # Should show 18 .png files

# Make sure they're named correctly
# Files should be .png (lowercase extension)
```

### ⚠️ "Job timed out after 3600s"

**Problem:** Pipeline took longer than 1 hour

**Causes:**
- System is low on resources
- COLMAP SFM failed on complex dataset
- Network issues

**Solutions:**
- Run with fewer images first to test
- Check system CPU/memory during run
- Increase timeout in `test_local_3d_generation.py`

### ❌ "Import errors" or "Module not found"

**Problem:** Python can't find backend modules

**Solutions:**
```bash
# Make sure you're in the project root directory
pwd    # Should show: .../photogrametry

# Verify venv is activated
which python    # Should show: .../venv/bin/python

# Reinstall packages if needed
pip install -r requirements.txt
```

## 📈 Performance Tips

### For Faster Results:
1. **Disable unnecessary features:**
   - Edit test script, set `enable_splat=False`
   - Comment out SPLAT stage to save 30sec

2. **Use GPU if available:**
   - COLMAP can use GPU for feature extraction
   - Requires CUDA/cuDNN setup

3. **Reduce image resolution:**
   - Pre-resize images before upload
   - Faster processing, lower quality results

### For Better Quality:
1. **Keep all images:**
   - More images = better reconstruction
   - Current: 17 (turtle), 18 (cube) is good

2. **Ensure good coverage:**
   - Images from different angles
   - No over/under exposure
   - Sharp, in-focus shots

## 📞 Getting Help

If you encounter issues:

1. **Check test output carefully** - Error messages usually indicate the problem
2. **Review backend logs** - Backend terminal shows detailed processing info
3. **Verify all prerequisites** are installed and running
4. **Try manual steps** - Run Step 1-3 manually to identify exact failure point
5. **Check disk space** - 3D model generation needs ~1-2 GB free space

## ✅ Validation Checklist

Before running tests:

- [ ] Backend code is in `backend/` folder
- [ ] Assets in `assets/turtle_images/` (17 files) and `assets/cube_images/` (18 files)
- [ ] venv is created and all 40 packages installed
- [ ] No other services using port 8000
- [ ] At least 2 GB free disk space
- [ ] System has at least 2 CPU cores and 4 GB RAM

## 🎯 Next Steps After Testing

Once models are generated:

1. **Check quality:** Open PLY/OBJ files in 3D viewer
   - Windows: Recommended free viewers: Meshlab, 3D Viewer
   - Online: Sketchfab, THREE.js viewers

2. **Verify correctness:**
   - Turtle model should show turtle object clearly
   - Cube model should show cube geometry correctly

3. **Prepare for deployment:**
   - Verify you have all necessary credentials
   - Test with Kaggle worker when ready
   - Set up production environment variables

---

**Status:** ✅ Ready to generate 3D models from assets

**Next Command:** 
```bash
python start_and_test.py
```
