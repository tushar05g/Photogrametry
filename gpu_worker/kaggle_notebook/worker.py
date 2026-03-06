"""
╔══════════════════════════════════════════════════════════╗
║   MORPHIC GPU WORKER v2.0 — GAUSSIAN SPLATTING ENGINE   ║
║             For Kaggle GPU Notebooks (T4/P100)           ║
╚══════════════════════════════════════════════════════════╝

🎓 TEACHER'S NOTE — HOW THIS WORKER FITS IN THE ARCHITECTURE:
==============================================================

This is a DISTRIBUTED WORKER. It is a completely separate Python script that runs
inside a Kaggle Notebook with GPU access. Here is its position in the system:

  [User's Browser] → [FastAPI Backend] → [Redis Queue] → [THIS WORKER]
                                              ↑
                                     This worker POLLS the queue

HOW THE PIPELINE WORKS (Gaussian Splatting Edition):
====================================================

TRADITIONAL PHOTOGRAMMETRY (old approach):
  photos → COLMAP → sparse point cloud → .PLY file (basic dots)

GAUSSIAN SPLATTING (our new approach):
  photos → COLMAP → sparse point cloud → 3D Gaussian model → Dense Mesh → .GLB

WHAT ARE "3D GAUSSIANS"?
  Imagine placing millions of tiny transparent "soap bubbles" in 3D space.
  Each bubble has:
    - A 3D position (x, y, z)
    - A shape (stretched like an egg or round like a ball)
    - A color / transparency
    - A "view-dependent" RGB color (changes as you rotate the camera)

  Neural networks learn to place these gaussians EXACTLY where they need to be
  to reconstruct the scene. The result looks photorealistic — much better than
  a sparse point cloud.

TOOL CHAIN:
  1. COLMAP         → Estimates camera poses from images (Structure-from-Motion)
  2. OpenSplat      → Trains 3D Gaussian Splatting model on the camera poses
  3. Open3D         → Converts the gaussian splats into a triangle mesh
  4. trimesh        → Exports the mesh as a .GLB file (for web browsers)
  5. Cloudinary     → Uploads file for the frontend to display

INSTALL INSTRUCTIONS FOR KAGGLE:
  Run this cell ONCE before the main script.
  See install_dependencies() for the exact commands.
"""

import os
import sys
import time
import json
import shutil
import subprocess
import requests
import io

# ─────────────────────────────────────────────────────────
# 🔧 CONFIGURATION — paste your values here
# ─────────────────────────────────────────────────────────
BACKEND_URL  = "https://ollie-unfashionable-topographically.ngrok-free.dev"  # 👈 Your PC's ngrok URL
WORKER_ID    = "kaggle-gpu-1"                            # 👈 Give this worker a name
POLL_INTERVAL = 15  # Seconds between polling for new jobs

# ☁️ Cloudinary — where we store the final .GLB model
CLOUD_NAME  = "dbvidngtc"
API_KEY     = "965528154675166"
API_SECRET  = "VimOI9Zi1dPIyc7x0rzC_JChl8I"


# ─────────────────────────────────────────────────────────
# 📦 DEPENDENCY INSTALLATION
# ─────────────────────────────────────────────────────────

def install_dependencies():
    """
    🎓 Installs all GPU tools needed for Gaussian Splatting.

    OPENSPLAT:
      A lightweight, open-source Gaussian Splatting trainer from Masaccio Labs.
      It is faster to install than Nerfstudio and works well on Kaggle's GPUs.
      GitHub: https://github.com/pierotofy/OpenSplat

    OPEN3D:
      A library for 3D data processing. We use it to convert gaussian splats
      into a dense triangle mesh via Poisson Surface Reconstruction.

    TRIMESH:
      A 3D mesh processing library. We use it to export the mesh as .GLB
      (GL Binary), which is the standard format for web-based 3D viewers (Three.js).
    """
    print("📋 Checking for Gaussian Splatting tools...")
    try:
        import open3d
        import trimesh
        import cloudinary
        import onnxruntime   # ← This is what rembg[gpu] provides. If missing, reinstall.
        import rembg
        print("✅ All dependencies cached and ready!")
        return
    except ImportError:
        pass

    print("⚙️ Installing Gaussian Splatting stack...")

    # System tools
    os.system("apt-get update -qq && apt-get install -y -qq colmap xvfb libgl1")

    # 🎓 WHY THIS ORDER MATTERS:
    # rembg 2.0.72+ now requires pillow>=12.1.0 AND numpy>=2.3.0
    # If we install pillow or numpy FIRST with old version pins, rembg install fails.
    # Solution: let rembg install FIRST and pull in its own compatible pillow/numpy.
    # Then install everything else without conflicting pins.

    # Step 1: Install rembg[gpu] — MUST include the [gpu] extra to get onnxruntime-gpu
    # Step 1: Install rembg[gpu] — MUST include the [gpu] extra to get onnxruntime-gpu
    # Kaggle Python 3.12 requires rembg >= 2.0.55.
    # To prevent numpy 2.x from breaking the pre-compiled Kaggle numba library (used by pymatting),
    # we force pip to reinstall numba against the current numpy, and pin pymatting to a stable version.
    os.system('pip install -q --no-warn-conflicts "rembg[gpu]" "numpy<2" "pymatting<=1.1.12" --ignore-installed numba')

    # Step 2: Install cloudinary (no version conflict)
    os.system("pip install -q cloudinary")

    # Step 3: OpenCV headless — must use headless to avoid PyQt5/GUI conflicts on Kaggle
    os.system("pip install -q --no-warn-conflicts opencv-python-headless")

    # Step 4: Mesh tools for Gaussian→GLB conversion
    # PyMeshLab = C++ MeshLab engine with Python bindings (no numpy conflicts)
    # trimesh   = lightweight Python mesh I/O and GLB export
    os.system("pip install -q pymeshlab trimesh")

    # Step 5: Nerfstudio for Gaussian Splatting (replaces opensplat)
    # splatfacto is the premier gaussian splatting model
    os.system("pip install -q nerfstudio gsplat")

    print("✅ All dependencies installed!")


# ─────────────────────────────────────────────────────────
# 🛰️ WORKER REGISTRATION
# ─────────────────────────────────────────────────────────

def register_worker():
    """
    🎓 Tells the backend: "I'm alive and at this URL."
    Since this is running inside Kaggle, we can't have a public URL.
    So we register by calling the backend's /workers/next-job endpoint directly.

    NOTE: In the "full" distributed mode, the worker would spin up its OWN FastAPI
    server, expose it via ngrok, and register that URL. For the Kaggle notebook,
    we use the simpler pull-based polling approach instead.
    """
    try:
        resp = requests.post(f"{BACKEND_URL}/workers/register", json={
            "worker_id": WORKER_ID,
            "url": "kaggle-pull-mode"  # We poll instead of receiving pushes
        }, timeout=10)
        if resp.status_code == 200:
            print(f"🛰️ Registered as worker '{WORKER_ID}'")
        else:
            print(f"⚠️ Registration response: {resp.status_code}")
    except Exception as e:
        print(f"⚠️ Could not register (backend may not have the /workers route yet): {e}")


# ─────────────────────────────────────────────────────────
# 🔄 JOB POLLING
# ─────────────────────────────────────────────────────────

def get_next_job():
    """
    🎓 Pulls the next available job from the backend.

    We use a "pull model": the worker asks for work instead of the backend
    pushing work to the worker. This is more resilient in distributed systems.

    Fallback: We also support the legacy /scans/next-pending endpoint
    for backward compatibility with the old polling approach.
    """
    try:
        resp = requests.get(f"{BACKEND_URL}/workers/next-job", params={"worker_id": WORKER_ID}, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("job_id"):
                return data
    except Exception:
        pass

    # Fallback: legacy polling
    try:
        resp = requests.get(f"{BACKEND_URL}/scans/next-pending", timeout=10)
        if resp.status_code == 200:
            job_data = resp.json()
            img_resp = requests.get(f"{BACKEND_URL}/scans/{job_data['id']}/images", timeout=10)
            return {
                "job_id": job_data["id"],
                "images": img_resp.json().get("images", []) if img_resp.ok else []
            }
    except Exception as e:
        raise e

    return None


def check_job_status(job_id: str) -> bool:
    """Returns True if the job is still active (not cancelled/failed)."""
    try:
        resp = requests.get(f"{BACKEND_URL}/scans/{job_id}", timeout=10)
        if resp.status_code == 200:
            status = resp.json().get("status", "")
            if status in ("cancelled", "failed"):
                print(f"🛑 Job {job_id} was marked '{status}' on server. Stopping worker.")
                return False
        return True
    except Exception:
        return True  # On network error, assume still active


def report_progress(job_id: str, **fields):
    """Sends a PATCH to update the job status on the backend."""
    try:
        requests.patch(f"{BACKEND_URL}/scans/{job_id}", json=fields, timeout=10)
    except Exception as e:
        print(f"⚠️ Failed to report progress: {e}")


def mark_worker_idle():
    """Tells the backend this worker is free for new jobs."""
    try:
        requests.post(f"{BACKEND_URL}/workers/{WORKER_ID}/idle", timeout=10)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
# ✂️  STAGE 0: BACKGROUND REMOVAL (rembg)
# ─────────────────────────────────────────────────────────

def download_and_mask_images(images: list, input_dir: str):
    """
    🎓 Downloads each image and removes the background using an AI model.

    WHY REMOVE BACKGROUNDS?
    COLMAP tries to match features (corners, edges) between photos.
    Background clutter (walls, floors, tables) creates "false" feature matches
    that confuse the reconstruction. Removing backgrounds focuses COLMAP on
    ONLY the object you care about. Result: much cleaner 3D models.

    """
    # Try to import rembg. It raises SystemExit(1) if onnxruntime is missing,
    # so we catch ImportError, SystemExit, and ValueError (numpy binary incompatibility)
    rembg_remove = None
    try:
        from rembg import remove as _rembg_remove
        from PIL import Image
        rembg_remove = _rembg_remove
    except Exception as e:
        print(f"   ⚠️ rembg unavailable ({type(e).__name__}: {str(e)[:50]}) — images will be downloaded without masking")

    warnings = []
    for i, url in enumerate(images):
        img_data = b""
        try:
            img_data = requests.get(url, timeout=30).content
            if rembg_remove is not None:
                masked_bytes = rembg_remove(img_data)
                from PIL import Image
                with Image.open(io.BytesIO(masked_bytes)) as img:
                    if img.mode in ("RGBA", "P"):
                        bg = Image.new("RGB", img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[3])
                        final = bg
                    else:
                        final = img.convert("RGB")
                    final.save(os.path.join(input_dir, f"img_{i:04d}.jpg"), "JPEG", quality=95)
                print(f"   ✂️  Masked {i+1}/{len(images)}")
            else:
                # No rembg — save original directly
                with open(os.path.join(input_dir, f"img_{i:04d}.jpg"), "wb") as f:
                    f.write(img_data)
                print(f"   📥 Downloaded {i+1}/{len(images)} (no masking)")
        except Exception as e:
            warnings.append(f"Image {i+1} error: {str(e)[:80]}")
            if img_data:
                with open(os.path.join(input_dir, f"img_{i:04d}.jpg"), "wb") as f:
                    f.write(img_data)

    return warnings



# ─────────────────────────────────────────────────────────
# 🧠 STAGE 1: CAMERA POSE ESTIMATION (COLMAP)
# ─────────────────────────────────────────────────────────

def run_colmap(input_dir: str, workspace: str):
    """
    🎓 COLMAP: Structure-from-Motion (SfM) Pipeline.

    WHAT IS SfM?
    Structure-from-Motion answers the question:
    "Given a set of 2D photos, where was the camera for EACH photo?"

    THREE STEPS INSIDE COLMAP:

    1. FEATURE EXTRACTION (feature_extractor):
       Runs the SIFT algorithm on each image to find thousands of "keypoints"
       — distinctive points like corners, blobs, or edges.
       Each keypoint gets a 128-dimensional descriptor (a fingerprint).

    2. FEATURE MATCHING (exhaustive_matcher):
       Compares the descriptors from ALL pairs of images.
       Finds which keypoints in Photo A correspond to the same physical point in Photo B.
       This is how COLMAP knows "this corner in image 3 is the same corner as image 7".

    3. MAPPING (mapper):
       Uses the matched keypoints to triangulate 3D positions.
       Like how your two eyes give you depth perception — two camera views give depth too.
       Output: sparse_model/ — a set of 3D points + camera poses.

    WHY GPU?
       SIFT matching is a massively parallel operation (compare N descriptors against M).
       On GPU it's ~10x faster than CPU. XVFB creates a virtual display so COLMAP
       can initialize GPU/OpenGL without a real monitor.
    """
    db_path = os.path.join(workspace, "database.db")
    sparse_dir = os.path.join(workspace, "sparse")
    os.makedirs(sparse_dir, exist_ok=True)

    xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]

    def run(cmd, timeout=600):
        import time
        import re
        
        process = subprocess.Popen(
            xvfb + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1
        )
        
        start_time = time.time()
        output = []
        last_progress_str = ""
        
        try:
            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                output.append(line)
                
                # Check for timeout manually since we're reading line by line
                if time.time() - start_time > timeout:
                    process.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout)

                # --- Parses COLMAP's output for live progress ---
                
                # Feature Extraction ("Processed file [X/Y]")
                if "Processed file" in line:
                    m = re.search(r"Processed file \[(\d+)/(\d+)\]", line)
                    if m:
                        curr, total = int(m.group(1)), int(m.group(2))
                        pct = int((curr / total) * 100)
                        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                        prog_str = f"\r   ⏳ Extracting: [{bar}] {pct}% ({curr}/{total})"
                        if prog_str != last_progress_str:
                            sys.stdout.write(prog_str)
                            sys.stdout.flush()
                            last_progress_str = prog_str
                            
                # Exhaustive Matching ("Matching block [X/Y, A/B]")
                elif "Matching block" in line:
                    m = re.search(r"Matching block \[(\d+)/(\d+), (\d+)/(\d+)\]", line)
                    if m:
                        # COLMAP matching blocks are usually 1/1 for small datasets, but
                        # it also outputs "Matching block [1/1, 1/1]" repeatedly for chunks inside
                        sys.stdout.write(f"\r   ⏳ Matching pairs: [████████████████████] (Running on GPU...)")
                        sys.stdout.flush()
                        
                # Alternative matcher output: "Matching image [X/Y]"
                elif "Matching image" in line:
                    m = re.search(r"Matching image \[(\d+)/(\d+)\]", line)
                    if m:
                        curr, total = int(m.group(1)), int(m.group(2))
                        pct = int((curr / total) * 100)
                        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                        prog_str = f"\r   ⏳ Matching: [{bar}] {pct}% ({curr}/{total})"
                        if prog_str != last_progress_str:
                            sys.stdout.write(prog_str)
                            sys.stdout.flush()
                            last_progress_str = prog_str

            process.wait()
            if last_progress_str:
                print()  # newline after progress bar ends
                
            if process.returncode != 0:
                full_log = "\\n".join(output[-30:])  # Show last 30 lines on crash
                raise RuntimeError(f"COLMAP failed:\\n{full_log}")
            
        except Exception as e:
            process.kill()
            raise e

    print("   🔍 Extracting features (SIFT)...")
    run(["colmap", "feature_extractor",
         "--database_path", db_path,
         "--image_path", input_dir,
         "--SiftExtraction.use_gpu", "1",
         "--SiftExtraction.max_image_size", "3200",
         "--SiftExtraction.max_num_features", "16384"])

    print("   🔗 Matching features between all image pairs...")
    run(["colmap", "exhaustive_matcher",
         "--database_path", db_path,
         "--SiftMatching.use_gpu", "1"], timeout=900)

    print("   📐 Reconstructing sparse 3D model...")
    run(["colmap", "mapper",
         "--database_path", db_path,
         "--image_path", input_dir,
         "--output_path", sparse_dir])

    print("   ✅ COLMAP complete!")
    return sparse_dir


# ─────────────────────────────────────────────────────────
# ✨ STAGE 2: TRAIN GAUSSIAN SPLATTING (Nerfstudio)
# ─────────────────────────────────────────────────────────

def run_nerfstudio(colmap_dir: str, workspace: str) -> str:
    """
    🎓 GAUSSIAN SPLATTING: splatfacto via Nerfstudio
    
    Nerfstudio is the industry standard framework for Neural Radiance Fields
    and Gaussian Splatting. 
    
    PIPELINE:
    1. ns-process-data: (Skipped) We already ran COLMAP manually in Stage 1.
    2. ns-train splatfacto: Trains the photometric 3D Gaussian model.
       It takes the camera poses and sparse points from COLMAP, and optimizes
       millions of 3D gaussians to match the training photos.
    3. ns-export gaussian-splat: Converts the trained model into a standard
       .ply file containing the gaussians (positions, colors, scales, rotations).
    """
    splat_output_dir = os.path.join(workspace, "splat_output")
    os.makedirs(splat_output_dir, exist_ok=True)
    splat_ply_path = os.path.join(splat_output_dir, "splat.ply")

    # 1. Train the model
    # We use --max-num-iterations 7000 for a good balance of speed (5-10m) and quality
    print("   ✨ Training Gaussian Splatting model (Nerfstudio splatfacto)...")
    train_cmd = [
        "ns-train", "splatfacto",
        "--data", colmap_dir,  # Point this to the root of where COLMAP ran
        "--max-num-iterations", "7000",
        "--viewer.quit-on-train-completion", "True",
        "--output-dir", splat_output_dir
    ]
    
    result = subprocess.run(train_cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        print(f"   ⚠️ ns-train failed. Showing tail of stderr:")
        print("\n".join(result.stderr.splitlines()[-30:]))
        raise RuntimeError(f"Nerfstudio training failed.")

    # Find the config.yml that ns-train just generated
    # It lives in splat_output/colmap_dir_name/splatfacto/.../config.yml
    import glob
    config_paths = glob.glob(os.path.join(splat_output_dir, "**", "config.yml"), recursive=True)
    if not config_paths:
        raise RuntimeError("Nerfstudio training completed, but cannot find config.yml to export model.")
    
    config_path = config_paths[0]
    print(f"   📦 Training complete. Exporting splat PLY...")

    # 2. Export the splat
    export_cmd = [
        "ns-export", "gaussian-splat",
        "--load-config", config_path,
        "--output-dir", splat_output_dir
    ]
    
    export_result = subprocess.run(export_cmd, capture_output=True, text=True, timeout=600)
    if export_result.returncode != 0:
        raise RuntimeError(f"ns-export failed:\\n{export_result.stderr[-500:]}")
        
    # ns-export saves to `splat_output_dir/splat.ply` by default
    final_ply = os.path.join(splat_output_dir, "splat.ply")
    if not os.path.exists(final_ply):
        raise RuntimeError("ns-export finished but splat.ply was not created.")

    print(f"   ✅ Gaussian model saved: {final_ply}")
    return final_ply


# ─────────────────────────────────────────────────────────
# 🏗️ STAGE 3: CONVERT SPLATS TO MESH → EXPORT .GLB
# ─────────────────────────────────────────────────────────

def splat_to_glb(splat_ply_path: str, workspace: str) -> str:
    """
    🎓 Converts a PLY point cloud → triangle mesh → GLB.

    WHY PyMeshLab INSTEAD OF Open3D?
    Open3D imports its own ML submodule (open3d.ml) which depends on sklearn,
    scipy, and numpy in very specific version ranges. Kaggle installs numpy 2.x
    which breaks scipy._lib._array_api, causing the entire open3d import to fail.

    PyMeshLab wraps the MeshLab C++ engine (the industry standard mesh processing
    tool) via Python bindings that have no numpy/scipy dependencies at runtime.
    It's more stable in heterogeneous environments like Kaggle.

    PIPELINE:
    1. Load PLY via PyMeshLab (handles both point clouds and meshes)
    2. Compute per-point normals (required for Poisson reconstruction)
    3. Run Screened Poisson Surface Reconstruction (state-of-the-art meshing)
    4. Save as .OBJ (intermediate universal format)
    5. Load OBJ with trimesh and export as .GLB (web-native binary format)
    """
    import trimesh

    glb_path = os.path.join(workspace, "model.glb")
    obj_path = os.path.join(workspace, "model.obj")

    try:
        import pymeshlab
        print("   🏗️ Loading point cloud with PyMeshLab...")
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(splat_ply_path)

        n_verts = ms.current_mesh().vertex_number()
        print(f"   📊 {n_verts:,} points loaded.")

        if n_verts == 0:
            raise RuntimeError("Point cloud is empty — COLMAP may have failed.")

        # Estimate vertex normals (required for Poisson reconstruction)
        print("   � Estimating surface normals...")
        ms.compute_normal_for_point_clouds(k=20)

        # Screened Poisson Surface Reconstruction
        # depth=9 → high quality mesh. Lower for speed, higher for more detail.
        print("   🌊 Running Poisson Surface Reconstruction...")
        ms.generate_surface_reconstruction_screened_poisson(depth=9)

        # Decimate mesh to ~100k faces for web performance and Cloudinary limits
        print("   📉 Decimating mesh to 100k faces for web...")
        try:
            ms.meshing_decimation_quadric_edge_collapse(targetfacenum=100000)
        except Exception as e:
            print(f"   ⚠️ Decimation failed: {e}")

        ms.save_current_mesh(obj_path)
        print(f"   💾 Saved OBJ ({os.path.getsize(obj_path) / 1024:.0f} KB)")

    except ImportError:
        print("   ℹ️ PyMeshLab not installed — using trimesh convex hull fallback...")
        # Trimesh can read PLY directly and produce a convex hull mesh
        pcd = trimesh.load(splat_ply_path)
        if hasattr(pcd, 'convex_hull'):
            mesh = pcd.convex_hull
        else:
            mesh = pcd
        mesh.export(obj_path, file_type='obj')

    # Load OBJ with trimesh and export as .GLB
    print("   📦 Converting OBJ → GLB...")
    scene_or_mesh = trimesh.load(obj_path)
    # trimesh.load returns a Scene if multi-mesh, extract or use directly
    if isinstance(scene_or_mesh, trimesh.Scene):
        glb_data = scene_or_mesh.export(file_type='glb')
    else:
        glb_data = scene_or_mesh.export(file_type='glb')

    with open(glb_path, 'wb') as f:
        f.write(glb_data)

    print(f"   ✅ GLB exported: {glb_path} ({os.path.getsize(glb_path)/1024/1024:.1f} MB)")
    return glb_path




# ─────────────────────────────────────────────────────────
# ☁️ STAGE 4: UPLOAD TO CLOUDINARY
# ─────────────────────────────────────────────────────────

def upload_glb(glb_path: str) -> str:
    """
    🎓 Uploads the final .GLB to Cloudinary.
    The URL is stored in the database so the frontend's Three.js viewer can load it.
    """
    import cloudinary
    import cloudinary.uploader

    print("   ☁️ Uploading .GLB to Cloudinary...")
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
    response = cloudinary.uploader.upload(
        glb_path,
        resource_type="raw",
        folder="3d_scanner_models",
        use_filename=True,
        unique_filename=True
    )
    url = response["secure_url"]
    print(f"   ✅ Uploaded: {url}")
    return url


# ─────────────────────────────────────────────────────────
# 🔥 MAIN JOB PROCESSOR
# ─────────────────────────────────────────────────────────

def process_job(job_id: str, images: list):
    """
    🎓 Orchestrates the full 3D reconstruction pipeline for a single job.
    Each stage can fail independently and reports its progress to the backend.
    """
    workspace = f"/kaggle/working/job_{job_id[:8]}"
    input_dir = os.path.join(workspace, "input")

    if os.path.exists(workspace):
        shutil.rmtree(workspace)
    os.makedirs(input_dir, exist_ok=True)

    try:
        # ── Stage 0: Background Removal ──
        report_progress(job_id, status="processing")
        print("✂️  [Stage 0] Background Removal...")
        warnings = download_and_mask_images(images, input_dir)
        if warnings:
            report_progress(job_id, warnings=" | ".join(warnings))

        if not check_job_status(job_id): return

        # ── Stage 1: COLMAP ──
        print("🧠 [Stage 1] Camera Pose Estimation (COLMAP)...")
        sparse_dir = run_colmap(input_dir, workspace)

        if not check_job_status(job_id): return

        # ── Stage 2: Gaussian Splatting Training ──
        print("✨ [Stage 2] Training Neural Splats (Nerfstudio)...")
        _update_status(job_id, "processing", "Training Neural Splats (Nerfstudio)")
        splat_ply = run_nerfstudio(workspace, workspace)

        if not check_job_status(job_id): return

        # ── Stage 3: Mesh + GLB Export ──
        print("🏗️  [Stage 3] Converting Splats → Mesh → GLB...")
        glb_path = splat_to_glb(splat_ply, workspace)

        if not check_job_status(job_id): return

        # ── Stage 4: Upload ──
        print("☁️  [Stage 4] Uploading to Cloudinary...")
        model_url = upload_glb(glb_path)

        # ── Done! ──
        report_progress(job_id, status="completed", model_url=model_url)
        print(f"\n🎉 Job {job_id[:8]} COMPLETE! Model URL: {model_url}\n")

    except subprocess.TimeoutExpired:
        error_msg = "Job timed out (>60 minutes). Try with fewer or smaller images."
        report_progress(job_id, status="failed", error_message=error_msg)
        print(f"⏰ {error_msg}")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"❌ Job failed:\n{tb}")
        report_progress(job_id, status="failed", error_message=str(e)[:500])
    finally:
        if os.path.exists(workspace):
            shutil.rmtree(workspace)
        mark_worker_idle()


# ─────────────────────────────────────────────────────────
# 🚀 MAIN LOOP
# ─────────────────────────────────────────────────────────

def start_worker():
    """
    🎓 The main polling loop.

    This worker is designed to run CONTINUOUSLY inside a Kaggle notebook:
    - It polls the backend every N seconds for new jobs.
    - When a job appears, it runs the entire pipeline.
    - When done, it loops back and waits for the next job.
    - The Kaggle session will keep running until you stop it or it times out (~12 hours).
    """
    install_dependencies()
    register_worker()

    print("\n📡 MORPHIC GPU WORKER v2.0 READY (Gaussian Splatting Mode)")
    print("─" * 55)
    print(f"  Backend: {BACKEND_URL}")
    print(f"  Worker:  {WORKER_ID}")
    print(f"  Polling: every {POLL_INTERVAL}s")
    print("─" * 55)
    print("Waiting for jobs... 🔄\n")

    while True:
        # Prevent disk full from crashed ghost jobs
        os.system("rm -rf /kaggle/working/job_* 2>/dev/null")
        
        try:
            job_data = get_next_job()
            if job_data and job_data.get("job_id"):
                job_id = job_data["job_id"]
                images = job_data.get("images", [])
                print(f"\n🔥 [JOB RECEIVED] {job_id[:8]}... ({len(images)} images)")
                process_job(job_id, images)
            else:
                print(f"   🌐 No jobs. Waiting {POLL_INTERVAL}s...", end="\r")
        except Exception as e:
            print(f"\n⚠️ Polling error: {e}")
        time.sleep(POLL_INTERVAL)


# ─── ENTRY POINT ───
if __name__ == "__main__":
    start_worker()
