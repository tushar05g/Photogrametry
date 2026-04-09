# Photogrammetry Testing Plan - Cube Images

## 🎯 Test Objectives

Validate the photogrammetry system's ability to reconstruct a simple geometric object (cube) from multiple 2D images, including both traditional mesh-based and modern Gaussian Splatting approaches.

### Key Goals
- Verify image upload and processing pipeline
- Validate 3D reconstruction accuracy for geometric shapes
- Test system performance with known object
- Validate output model quality and format (mesh + splat)
- Document processing time and resource usage
- **Test Gaussian Splatting generation and fallback mechanisms**
- Compare mesh vs. splat output quality

---

## 📊 Test Environment

### Available Assets
- **Location**: `assets/cube_images/`
- **Image Count**: 19 images (cube1.png through cube20.png, missing cube6.png and cube17.png)
- **Image Format**: PNG
- **Average File Size**: ~4MB per image
- **Object Type**: Simple geometric cube with distinct faces

### System Requirements
- Backend: `http://localhost:8000`
- Redis: `localhost:6379`
- Worker: Running and connected to Redis
- Storage: Configured (Cloudinary or local)

---

## 🎨 Gaussian Splatting Overview

### What is Gaussian Splatting?
Gaussian Splatting (3DGS) is a modern 3D rendering technique that represents scenes as millions of 3D Gaussian primitives instead of traditional mesh triangles. This produces more photorealistic results compared to mesh-based reconstruction.

### How It Works in This System

**Two Modes**:

1. **Full Gaussian Splatting Training** (if `SPLAT_TRAIN_CMD` configured):
   - Runs actual 3D Gaussian Splatting training (e.g., using gsplat or nerfstudio)
   - Trains for configurable iterations (default: 3000)
   - Produces high-quality photorealistic output
   - Requires GPU resources via Modal
   - Slower but best quality

2. **Fallback Conversion** (default mode):
   - Converts existing dense point cloud or mesh to simplified splat format
   - Creates `.splat` file (NPZ format) with Gaussian parameters
   - Generates preview files (PLY, GLB) for web viewing
   - Faster but less photorealistic than full training
   - Used when training command not configured or fails

**Output Files**:
- `model.splat` - Main splat artifact (NPZ format with xyz, rgb, opacity, scale, rotation)
- `model_splat_preview.ply` - Point cloud preview
- `model_splat_preview.glb` - Web-viewable 3D model

**Configuration** (via environment variables):
- `SPLAT_TRAIN_CMD` - Custom training command path
- `SPLAT_ITERATIONS` - Training steps (default: 3000)
- `SPLAT_MAX_POINTS` - Max points in fallback (default: 200000)
- `SPLAT_ALLOW_FALLBACK` - Allow fallback if training fails (default: true)

**Pipeline Position**:
- Runs after MVS and MESH stages
- Controlled by `enable_splat` parameter (default: true)
- Stage name: `SPLAT`
- Can be disabled by setting `enable_splat=False` in pipeline initiation

---

## 🧪 Test Scenarios

### Scenario 1: Minimum Image Set (Basic Test)
**Purpose**: Test with minimum required images
- **Images**: cube1.png, cube2.png, cube3.png (3 images)
- **Expected**: Job creation, processing initiation, basic reconstruction
- **Validation**: Job moves from PENDING to IN_PROGRESS to COMPLETED

### Scenario 2: Optimal Image Set (Recommended)
**Purpose**: Test with optimal number of images for best results
- **Images**: All 19 available cube images
- **Expected**: High-quality 3D reconstruction with accurate geometry
- **Validation**: Complete cube shape with all faces visible

### Scenario 3: Partial Coverage Test
**Purpose**: Test with images covering limited angles
- **Images**: cube1.png, cube2.png, cube4.png, cube5.png (4 images, similar angles)
- **Expected**: Partial reconstruction with missing faces
- **Validation**: System handles incomplete coverage gracefully

### Scenario 4: Progressive Upload Test
**Purpose**: Test single image upload workflow
- **Method**: Use `/init` endpoint, then upload images individually via `/{job_id}/upload-single`
- **Expected**: Job created, images uploaded one by one, manual pipeline start
- **Validation**: Flexible upload workflow

### Scenario 5: Splatting Enabled (Default)
**Purpose**: Test Gaussian Splatting generation with fallback mode
- **Images**: All 19 cube images
- **Configuration**: `enable_splat=True` (default)
- **Expected**: Pipeline runs SPLAT stage, generates .splat file + previews
- **Validation**: SPLAT stage completes, splat files uploaded to storage

### Scenario 6: Splatting Disabled
**Purpose**: Test traditional mesh-only pipeline without splatting
- **Images**: All 19 cube images
- **Configuration**: `enable_splat=False`
- **Expected**: Pipeline stops after MESH, no SPLAT stage
- **Validation**: Job completes without splat stage, only mesh output

### Scenario 7: Mesh vs. Splat Comparison
**Purpose**: Compare quality between traditional mesh and splat outputs
- **Method**: Run two identical jobs - one with splatting, one without
- **Images**: Same 19 cube images for both jobs
- **Expected**: Both complete successfully, different output formats
- **Validation**: Compare visual quality, file sizes, processing times

### Scenario 8: Splatting with Sparse Fallback
**Purpose**: Test splatting when dense reconstruction fails
- **Images**: Minimum set (3 images) - may produce poor dense reconstruction
- **Configuration**: `enable_splat=True`
- **Expected**: SPLAT stage falls back to sparse point cloud
- **Validation**: SPLAT completes using sparse points, not dense

---

## 📋 Test Execution Steps

### Pre-Test Setup
```bash
# 1. Verify system status
curl http://localhost:8000/health
redis-cli ping

# 2. Check worker status
ps aux | grep worker

# 3. Review available cube images
ls -lh assets/cube_images/
```

### Test Case 1: Full Cube Reconstruction (Primary Test)

#### Step 1: Upload All Cube Images
```bash
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "project_name=Cube Test Full" \
  -F "files=@assets/cube_images/cube1.png" \
  -F "files=@assets/cube_images/cube2.png" \
  -F "files=@assets/cube_images/cube3.png" \
  -F "files=@assets/cube_images/cube4.png" \
  -F "files=@assets/cube_images/cube5.png" \
  -F "files=@assets/cube_images/cube7.png" \
  -F "files=@assets/cube_images/cube8.png" \
  -F "files=@assets/cube_images/cube9.png" \
  -F "files=@assets/cube_images/cube10.png" \
  -F "files=@assets/cube_images/cube11.png" \
  -F "files=@assets/cube_images/cube12.png" \
  -F "files=@assets/cube_images/cube13.png" \
  -F "files=@assets/cube_images/cube14.png" \
  -F "files=@assets/cube_images/cube15.png" \
  -F "files=@assets/cube_images/cube16.png" \
  -F "files=@assets/cube_images/cube18.png" \
  -F "files=@assets/cube_images/cube19.png" \
  -F "files=@assets/cube_images/cube20.png"
```

#### Step 2: Capture Job ID
- Save the returned `job_id` for monitoring
- Example: `{"job_id":"abc-123-def", ...}`

#### Step 3: Monitor Job Progress
```bash
# Check status every 30 seconds
curl "http://localhost:8000/api/v1/scans/{job_id}/status"

# Monitor worker logs
tail -f worker.log
```

#### Step 4: Track Processing Stages
Expected stages:
1. `IDLE` → Job created
2. `IMAGE_VALIDATION` → Validating uploaded images
3. `FEATURE_EXTRACTION` → SIFT keypoint detection
4. `FEATURE_MATCHING` → Pairwise image matching
5. `SFM` → Structure from Motion
6. `MVS` → Multi-View Stereo
7. `MESHING` → Surface reconstruction
8. `TEXTURING` → Applying textures
9. `COMPLETED` → Job finished

#### Step 5: Retrieve Results
```bash
# Get job results with model URLs
curl "http://localhost:8000/api/v1/scans/{job_id}/results"
```

#### Step 6: Download and Verify 3D Model
```bash
# Download the generated model
curl "http://localhost:8000/api/v1/jobs/{job_id}/download" -o cube_model.obj

# Or view in web interface
# Open http://localhost:8000 in browser and navigate to job
```

### Test Case 5: Splatting Enabled (Default)
```bash
# Upload with splatting enabled (default)
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "project_name=Cube Test Splat Enabled" \
  -F "files=@assets/cube_images/cube1.png" \
  -F "files=@assets/cube_images/cube2.png" \
  -F "files=@assets/cube_images/cube3.png" \
  -F "files=@assets/cube_images/cube4.png" \
  -F "files=@assets/cube_images/cube5.png" \
  -F "files=@assets/cube_images/cube7.png" \
  -F "files=@assets/cube_images/cube8.png" \
  -F "files=@assets/cube_images/cube9.png" \
  -F "files=@assets/cube_images/cube10.png"

# Monitor for SPLAT stage in progress
curl "http://localhost:8000/api/v1/scans/{job_id}/status"

# Check results for splat files
curl "http://localhost:8000/api/v1/scans/{job_id}/results"
```

### Test Case 6: Splatting Disabled
```bash
# Upload with splatting disabled (requires direct API call to worker)
# Note: The current API always enables splatting by default
# To disable, you would need to modify the pipeline initiation or use worker directly

# Alternative: Compare job stages - SPLAT stage should not appear
curl "http://localhost:8000/api/v1/scans/{job_id}/status" | grep SPLAT
# Should return empty if splatting is disabled
```

### Test Case 7: Mesh vs. Splat Comparison
```bash
# Run job with splatting (Job A)
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "project_name=Cube Test With Splat" \
  -F "files=@assets/cube_images/cube1.png" \
  ... (all 19 images)
# Save job_id as JOB_WITH_SPLAT

# Wait for completion, then get results
curl "http://localhost:8000/api/v1/scans/$JOB_WITH_SPLAT/results"

# Compare processing times, file sizes, and visual quality
```

### Test Case 2: Minimum Image Set
```bash
curl -X POST http://localhost:8000/api/v1/jobs/upload \
  -F "project_name=Cube Test Minimum" \
  -F "files=@assets/cube_images/cube1.png" \
  -F "files=@assets/cube_images/cube2.png" \
  -F "files=@assets/cube_images/cube3.png"
```

### Test Case 3: Progressive Upload
```bash
# Step 1: Initialize job
curl -X POST "http://localhost:8000/api/v1/jobs/init" \
  -F "project_name=Cube Test Progressive"

# Step 2: Upload images individually (repeat for each image)
curl -X POST "http://localhost:8000/api/v1/jobs/{job_id}/upload-single" \
  -F "file=@assets/cube_images/cube1.png"

# Step 3: Start pipeline
curl -X POST "http://localhost:8000/api/v1/jobs/{job_id}/start"
```

---

## ✅ Validation Criteria

### Functional Validation
- [ ] Job successfully created in database
- [ ] Images uploaded to storage without errors
- [ ] Worker picks up job from queue
- [ ] Processing progresses through all stages
- [ ] Job status changes: PENDING → IN_PROGRESS → COMPLETED/FAILED
- [ ] 3D model files generated (OBJ, PLY, or GLB format)

### Quality Validation
- [ ] **Geometry**: Cube shape recognizable with 6 faces
- [ ] **Completeness**: All or most cube faces visible
- [ ] **Scale**: Proportions roughly correct (cube-like, not flattened)
- [ ] **Surface**: Mesh is watertight (no major holes)
- [ ] **Texture**: Colors/patterns from images applied
- [ ] **Orientation**: Model is upright and properly aligned

### Splatting-Specific Validation
- [ ] **SPLAT Stage**: SPLAT stage appears in pipeline and completes
- [ ] **Splat File**: `model.splat` file generated and uploaded
- [ ] **Preview Files**: `model_splat_preview.ply` and `model_splat_preview.glb` generated
- [ ] **Point Count**: Splat contains reasonable number of points (check splat_metrics)
- [ ] **Fallback Behavior**: Falls back to sparse points if dense reconstruction fails
- [ ] **Format Validity**: .splat file is valid NPZ format
- [ ] **Web Viewable**: GLB preview can be viewed in web interface
- [ ] **Metrics**: Splat metrics recorded (num_points, duration_s, train_steps)

### Performance Validation
- [ ] Processing time recorded
- [ ] Memory usage within acceptable limits
- [ ] No worker crashes or timeouts
- [ ] CPU utilization reasonable

### Output Format Validation
- [ ] Model file is valid format (can be opened in viewer)
- [ ] File size reasonable (not corrupted)
- [ ] Model can be loaded in 3D viewer
- [ ] Interactive features work (rotate, zoom, pan)

---

## 📈 Expected Results

### Success Indicators
- Job completes within 5-15 minutes (for 19 images)
- Generated 3D model shows clear cube geometry
- Model has recognizable features from source images
- Model can be viewed and manipulated in web interface
- No error messages in worker logs

### Splatting Success Indicators
- SPLAT stage completes successfully
- `model.splat` file generated (size > 0)
- Preview files (PLY, GLB) generated and viewable
- Splat metrics show reasonable point count (> 1000 points)
- Splat file can be loaded in splat viewer
- Processing time for SPLAT stage reasonable (< 5 minutes for fallback mode)

### Failure Indicators
- Job status stuck at PENDING or IDLE
- Worker not processing job (check Redis connection)
- Processing fails at specific stage (check logs)
- Generated model is corrupted or unviewable
- Memory errors or timeouts during processing

---

## 🔍 Monitoring Commands

### Real-time Monitoring
```bash
# Watch job status
watch -n 5 'curl -s "http://localhost:8000/api/v1/scans/{job_id}/status"'

# Monitor worker activity
tail -f worker.log

# Check Redis queue
redis-cli llen "celery"

# Check database for job
sqlite3 photogrammetry.db "SELECT * FROM scan_jobs ORDER BY created_at DESC LIMIT 1;"
```

### Debugging Commands
```bash
# Check all jobs
curl "http://localhost:8000/api/v1/scans/"

# Get detailed job info
curl "http://localhost:8000/api/v1/scans/{job_id}"

# Check worker connectivity
redis-cli ping

# View recent errors
grep -i error worker.log | tail -20
```

---

## 🐛 Troubleshooting

### Issue: Job Stuck at PENDING
**Cause**: Worker not running or not connected to Redis
**Solution**: 
```bash
# Check worker process
ps aux | grep worker

# Restart worker
python core/workers/cpu_worker.py

# Verify Redis
redis-cli ping
```

### Issue: Processing Fails at Specific Stage
**Cause**: Image quality issues, insufficient coverage, or system resources
**Solution**:
- Check worker logs for specific error
- Verify image quality and coverage
- Reduce image count if memory issues
- Check available disk space

### Issue: Generated Model Poor Quality
**Cause**: Insufficient image overlap or poor angles
**Solution**:
- Use more images with better coverage
- Ensure 60-80% overlap between images
- Check lighting and focus in source images
- Try different image subset

### Issue: SPLAT Stage Fails
**Cause**: Insufficient geometry points, Modal GPU issues, or configuration errors
**Solution**:
- Check worker logs for specific error in SPLAT stage
- Verify dense reconstruction completed successfully
- Check Modal GPU availability and configuration
- Verify SPLAT_ALLOW_FALLBACK is set to true
- Check SPLAT_MAX_POINTS configuration
- If using custom trainer, verify SPLAT_TRAIN_CMD is correct

### Issue: Splat File Not Generated
**Cause**: SPLAT stage skipped, failed, or not enabled
**Solution**:
- Verify enable_splat=True in pipeline initiation
- Check job results for splat_url field
- Verify SPLAT stage appears in job stages
- Check if dense/mesh reconstruction failed (splat depends on these)
- Review worker logs for SPLAT-specific errors

### Issue: Splat Preview Files Missing
**Cause**: Preview generation failed or skipped
**Solution**:
- Check worker logs for preview generation errors
- Verify main splat file was generated successfully
- Check if trimesh library is installed and working
- GLB preview may fail if scene export fails (PLY should still work)

### Issue: Splat Point Count Too Low
**Cause**: Poor reconstruction quality or too aggressive downsampling
**Solution**:
- Increase SPLAT_MAX_POINTS environment variable
- Improve image quality and coverage
- Check if fallback to sparse points occurred
- Verify dense reconstruction quality

### Issue: Upload Fails
**Cause**: File size limits, network issues, or storage problems
**Solution**:
- Check file sizes (should be < 10MB each)
- Verify storage configuration in .env
- Check backend logs for upload errors

---

## 📊 Test Results Template

### Test Execution Log
| Test Case | Job ID | Image Count | Start Time | End Time | Duration | Status | Notes |
|-----------|--------|-------------|------------|----------|----------|--------|-------|
| Full Cube | | 19 | | | | | |
| Minimum Set | | 3 | | | | | |
| Progressive | | 19 | | | | | |

### Quality Assessment
| Metric | Rating (1-5) | Notes |
|--------|--------------|-------|
| Geometry Accuracy | | |
| Face Completeness | | |
| Surface Quality | | |
| Texture Mapping | | |
| Overall Quality | | |

### Performance Metrics
- **Processing Time**: ___ minutes
- **Peak Memory Usage**: ___ MB
- **CPU Utilization**: ___ %
- **Output File Size**: ___ MB

### Splatting Metrics
- **SPLAT Stage Duration**: ___ seconds
- **Splat Point Count**: ___ points
- **Splat File Size**: ___ MB
- **Splat Mode**: [ ] Full Training [ ] Fallback Conversion
- **Preview Files Generated**: [ ] PLY [ ] GLB

---

## 🎯 Success Criteria

The photogrammetry system is considered successfully tested if:
1. ✅ At least one test case completes successfully
2. ✅ Generated 3D model is viewable and recognizable as a cube
3. ✅ Processing completes without critical errors
4. ✅ Model can be downloaded and opened in external viewers
5. ✅ Web interface displays the model correctly
6. ✅ SPLAT stage executes and generates splat files (when enabled)
7. ✅ Splat preview files are viewable in web interface
8. ✅ Both mesh and splat outputs are accessible via API

---

## 📝 Next Steps After Testing

1. **Document Results**: Record all test outcomes in this file
2. **Archive Models**: Save successful models for reference
3. **Compare Results**: Analyze differences between test cases
4. **Optimize**: Adjust parameters based on test results
5. **Expand Testing**: Test with more complex objects

---

## 🔄 Regression Testing

For future system changes, re-run:
- Test Case 1 (Full Cube Reconstruction)
- Validate against recorded success criteria
- Compare processing times and output quality
- Document any performance changes

---

**Test Plan Created**: April 8, 2026  
**Test Assets**: assets/cube_images/ (19 PNG files)  
**System Version**: Morphic 3D Scanner v9.0.0
