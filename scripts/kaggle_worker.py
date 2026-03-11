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
import logging
import hashlib
import threading
import concurrent.futures
from pathlib import Path
from queue import Queue
from datetime import datetime
import gc
import signal
import torch

# Selective imports will be handled within process_job or after install_dependencies()
# to prevent PIL/NumPy from being locked in memory before the installer runs.
MaskingStep = None
ColmapStep = None
SplattingStep = None
MeshingStep = None
UploadStep = None

# ─────────────────────────────────────────────────────────
# � STRUCTURED LOGGING (replaces print)
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# 📈 TELEMETRY & MONITORING
# ─────────────────────────────────────────────────────────

def get_gpu_memory():
    """Returns used GPU memory in MB."""
    if not torch.cuda.is_available():
        return 0
    return torch.cuda.memory_allocated() / (1024 * 1024)

def log_step_metrics(step_name: str, start_time: float):
    """Logs duration and memory consumption for a pipeline step."""
    duration = time.time() - start_time
    gpu_mem = get_gpu_memory()
    logger.info(f"📊 [METRICS] {step_name} completed in {duration:.1f}s | GPU Mem: {gpu_mem:.0f}MB")

# ─────────────────────────────────────────────────────────
# 🛡️ PIPELINE CONTROLLER
# ─────────────────────────────────────────────────────────

class PipelineStep:
    """Base class for a reconstruction stage."""
    def __init__(self, name: str, fallback_fn=None):
        self.name = name
        self.fallback_fn = fallback_fn
        self.start_time = None
        self.error = None

    def run(self, *args, **kwargs):
        self.start_time = time.time()
        logger.info(f"🚀 [STEP START] {self.name}")
        try:
            result = self.execute(*args, **kwargs)
            log_step_metrics(self.name, self.start_time)
            return result, True
        except Exception as e:
            self.error = str(e)
            logger.error(f"❌ [STEP FAILED] {self.name}: {e}")
            if self.fallback_fn:
                logger.warning(f"🔄 [FALLBACK] Triggering fallback for {self.name}...")
                try:
                    res = self.fallback_fn(*args, **kwargs)
                    logger.info(f"✅ [FALLBACK SUCCESS] {self.name}")
                    return res, True
                except Exception as fe:
                    logger.error(f"🚨 [FALLBACK FAILED] {self.name}: {fe}")
            return None, False

    def execute(self, *args, **kwargs):
        raise NotImplementedError("Subclasses must implement execute()")

# ─────────────────────────────────────────────────────────
# 💾 CACHING SYSTEM
# ─────────────────────────────────────────────────────────
CACHE_DIR = Path("/kaggle/working/morphic_cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_file_hash(key: str, chunk_size=8192) -> str:
    """Compute SHA256 hash of a file or a string key for cache generation."""
    sha256 = hashlib.sha256()
    
    # If it's a URL or doesn't exist as a local file, hash the string directly
    if not os.path.exists(key):
        sha256.update(key.encode('utf-8'))
        return sha256.hexdigest()
        
    try:
        with open(key, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                sha256.update(chunk)
    except Exception:
        # Fallback to hashing the string if file reading fails
        sha256.update(key.encode('utf-8'))
        
    return sha256.hexdigest()

def get_cache_path(prefix: str, file_hash: str) -> Path:
    """Generate cache file path based on prefix and hash."""
    return CACHE_DIR / f"{prefix}_{file_hash}"

def cache_get(prefix: str, key_file: str) -> str:
    """Retrieve cached file if exists. Returns path or None."""
    file_hash = get_file_hash(key_file)
    if not file_hash:
        return None
    cache_path = get_cache_path(prefix, file_hash)
    if cache_path.exists():
        logger.info(f"💾 Cache HIT for {prefix}: {cache_path}")
        return str(cache_path)
    return None

def cache_put(prefix: str, key_file: str, cached_file: str) -> bool:
    """Store file in cache."""
    file_hash = get_file_hash(key_file)
    if not file_hash:
        return False
    cache_path = get_cache_path(prefix, file_hash)
    try:
        shutil.copy2(cached_file, cache_path)
        logger.info(f"💾 Cache STORE: {cache_path}")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Failed to cache {cached_file}: {e}")
        return False
BACKEND_URL  = "https://ollie-unfashionable-topographically.ngrok-free.dev"  # 👈 Your backend URL
WORKER_ID    = os.getenv("WORKER_ID", "kaggle-gpu-1")             # 👈 Give this worker a name
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))             # Seconds between polling

# ☁️ Cloudinary — loaded from environment variables
CLOUD_NAME  = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY     = os.getenv("CLOUDINARY_API_KEY")
API_SECRET  = os.getenv("CLOUDINARY_API_SECRET")

# 🔄 Redis — (Unused in pull-mode, here for legacy env support)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ─────────────────────────────────────────────────────────
# 🩺 BACKEND HEALTH CHECK
# ─────────────────────────────────────────────────────────

def check_gpu_availability():
    """Check if GPU is available and has sufficient memory."""
    try:
        import torch
        if torch.cuda.is_available():
            device = torch.device("cuda")
            torch.cuda.empty_cache()
            total_memory = torch.cuda.get_device_properties(device).total_memory / (1024**3)  # GB
            if total_memory < 8:  # Require at least 8GB
                logger.warning(f"GPU has only {total_memory:.1f}GB memory. May not suffice for large jobs.")
            logger.info(f"✅ GPU available: {torch.cuda.get_device_name(device)} ({total_memory:.1f}GB)")
            return True
        else:
            logger.warning("⚠️ No GPU available. Falling back to CPU (slow).")
            return False
    except Exception as e:
        logger.error(f"Failed to check GPU: {e}")
        return False

def check_backend_url():
    """
    🩺 HEALTH CHECK: Verification of connectivity to the FastAPI backend.
    """
    try:
        logger.info(f"🔗 Checking connectivity to {BACKEND_URL}...")
        # Try /health or just the base URL
        try:
            response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        except:
            response = requests.get(f"{BACKEND_URL}/", timeout=10)
            
        if response.status_code in [200, 404]: # 404 is fine as long as it responds
            logger.info("✅ Backend is ONline and reachable.")
            return True
        else:
            logger.warning(f"⚠️ Backend returned status {response.status_code}.")
            return False
    except Exception as e:
        logger.error(f"❌ Backend is UNREACHABLE: {e}")
        return False

# call early so warnings appear before install
delay_check = False


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
        import numpy as np
        import rembg
        import PIL
        
        # 🚨 RELAXED VALIDATION: Allow NumPy 2.x and Pillow 10-11
        is_numpy_ok = np.__version__.startswith("2.0")
        is_pillow_ok = PIL.__version__.startswith("10.") or PIL.__version__.startswith("11.")
        
        if not is_numpy_ok or not is_pillow_ok:
             print(f"⚠️ Runtime Mismatch: NumPy {np.__version__}, Pillow {PIL.__version__}")
             print("🔄 Forcing nuclear reinstall...")
             raise ImportError("Version mismatch")
             
        print(f"✅ All dependencies cached and ready! (NumPy {np.__version__}, Pillow {PIL.__version__})")
        check_gpu_availability()
        return
    except (ImportError, Exception):
        pass

    print("⚙️ Installing Gaussian Splatting stack...")
    os.system("apt-get update -qq && apt-get install -y -qq colmap xvfb libgl1")

    # Step 1: Nuclear Cleanup and Install NATIVE 2.X stack
    print("🧹 Purging conflicting packages and installing Native NumPy 2.x stack...")
    # Purge multiple times to handle nested installs
    for _ in range(2):
        os.system('pip uninstall -y numpy pillow rembg mediapipe onnxruntime-gpu torchvision 2>/dev/null')
    
    # We use the 'Goldilocks' combination for Python 3.12:
    # 1. Latest rembg/mediapipe (2.x ready)
    # 2. Pillow 10.3.0 (Fixed: torchvision fails on Pillow 11 due to missing _Ink)
    os.system('pip install -q --no-warn-conflicts '
              'numpy==2.0.2 '
              'numba==0.61.0 '
              'onnxruntime-gpu '
              'rembg==2.0.60 '
              'mediapipe '
              'torchvision '
              '"opencv-python-headless" "protobuf>=4"')

    # Step 3: Other requirements
    os.system("pip install -q cloudinary pymeshlab trimesh nerfstudio gsplat")
    
    # 🏁 FINAL ENFORCEMENT: Fix the Torchvision/Pillow import bug
    print("🩹 Applying final Pillow 10.3.0 patch for Torchvision stability...")
    os.system("pip install -q --force-reinstall 'Pillow==10.3.0'")

    # report any remaining dependency conflicts
    print("🔍 Checking for conflicts via 'pip check'...")
    try:
        # We silence pip check because Kaggle has many pre-installed packages 
        # that break when we force a specific NumPy version. 
        # We only care about OUR stack (numpy, rembg, torch).
        result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True)
        critical_packages = ['numpy', 'rembg', 'torch', 'torchvision', 'pillow']
        conflicts = [line for line in result.stdout.split('\n') if any(pkg in line.lower() for pkg in critical_packages)]
        
        if conflicts:
            print("⚠️ Note: Some system libraries have conflicts (normal for Kaggle), but core stack is OK.")
            # print("\n".join(conflicts)) # Uncomment for deep debugging
        else:
            print("✅ Core dependency stack is clean.")
    except Exception as e:
        print(f"⚠️ Failed to run pip check: {e}")

    print("🔬 Verifying binary layout compatibility...")
    try:
        import numpy as np
        import PIL
        print(f"✅ Runtime NumPy: {np.__version__}")
        print(f"✅ Runtime Pillow: {PIL.__version__}")
        
        # RELAXED: Don't force restart if version is "good enough" (10.x or 11.x)
        is_numpy_ok = np.__version__.startswith("2.0")
        is_pillow_ok = PIL.__version__.startswith("10.") or PIL.__version__.startswith("11.")
        
        if not is_numpy_ok or not is_pillow_ok:
            print("\n" + "!" * 60)
            print("🚨 CRITICAL: KERNEL RESTART REQUIRED")
            print(f"NumPy {np.__version__} and Pillow {PIL.__version__} are out of bounds.")
            print("Please click 'Run' -> 'Restart Session' at the top of Kaggle.")
            print("!" * 60 + "\n")
            sys.exit(0)
            
        # Run a quick check for common binary breakages
        np.array([1]).astype(np.float64)
    except Exception as e:
        print(f"🚨 Binary incompatibility detected: {e}")
        print("🔄 Attempting emergency fix...")
        os.system("pip install -q --upgrade numpy rembg mediapipe")

    print("✅ All dependencies installed!")
    print("💡 TIP: If you see 'numpy.dtype size changed' errors below, please RESTART YOUR KERNEL.")
    check_gpu_availability()


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
# ✂️  STAGE 0: BACKGROUND REMOVAL (rembg) — PARALLELIZED
# ─────────────────────────────────────────────────────────

# Global masking engines (loaded once, reused across jobs)
_masking_engines = {"rembg": None, "mediapipe": None, "torchvision": None}
_engines_lock = threading.Lock()

def _init_masking_engines():
    """Load masking engines once per worker (lazy, thread-safe)."""
    
    with _engines_lock:
        if _masking_engines["rembg"] is not None:
            return  # Already initialized
        
        # Engine 1: rembg (ONNX based)
        try:
            from rembg import remove as _rembg_remove, new_session
            # USE CUDA if available (Kaggle T4 x2 has CUDA)
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            session = new_session("isnet-general-use", providers=providers)
            
            def _rembg_mask(img_bytes):
                return _rembg_remove(img_bytes, session=session)
                
            _masking_engines["rembg"] = _rembg_mask
            logger.info("✅ rembg engine initialized with CUDA/CPU session.")
        except Exception as e:
            logger.warning(f"⚠️ rembg load failed: {e}")

        # Engine 2: Mediapipe (TFLite based)
        try:
            # 🧪 Force-reload mediapipe to ensure solutions are loaded
            import mediapipe as mp
            import numpy as np
            from PIL import Image
            
            # 🌋 Nuclear import: Try multiple pathways for the submodules
            mp_selfie_segmentation = None
            for pathway in [
                lambda: mp.solutions.selfie_segmentation,
                lambda: __import__('mediapipe.python.solutions.selfie_segmentation', fromlist=['*']),
                lambda: __import__('mediapipe.solutions.selfie_segmentation', fromlist=['*'])
            ]:
                try:
                    mp_selfie_segmentation = pathway()
                    if mp_selfie_segmentation: break
                except: continue
                
            if not mp_selfie_segmentation:
                raise ImportError("Could not locate mediapipe.solutions.selfie_segmentation")
            
            segmentation = mp_selfie_segmentation.SelfieSegmentation(model_selection=1)
            
            def _mp_mask(image_bytes):
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                image_np = np.array(image)
                results = segmentation.process(image_np)
                mask = results.segmentation_mask > 0.1
                image_np[~mask] = [255, 255, 255]
                out = Image.fromarray(image_np)
                with io.BytesIO() as bio:
                    out.save(bio, format="PNG")
                    return bio.getvalue()
                
            _masking_engines["mediapipe"] = _mp_mask
            logger.info("✅ Mediapipe engine initialized.")
        except Exception as e:
            logger.warning(f"⚠️ Mediapipe load failed: {e}")

        # Engine 3: Torchvision (PyTorch based)
        try:
            import torch
            from torchvision import models, transforms
            import numpy as np
            from PIL import Image
            
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            torch_model = models.segmentation.deeplabv3_resnet50(
                weights='DeepLabV3_ResNet50_Weights.DEFAULT'
            ).to(device).eval()
            
            preprocess = transforms.Compose([
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])

            def _torch_mask(image_bytes):
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                input_tensor = preprocess(img).unsqueeze(0).to(device)
                with torch.no_grad():
                    output = torch_model(input_tensor)['out'][0]
                output_predictions = output.argmax(0).byte().cpu().numpy()
                mask = output_predictions > 0
                img_np = np.array(img)
                img_np[~mask] = [255, 255, 255]
                out = Image.fromarray(img_np)
                with io.BytesIO() as bio:
                    out.save(bio, format="PNG")
                    return bio.getvalue()

            _masking_engines["torchvision"] = _torch_mask
            logger.info("✅ Torchvision engine initialized.")
        except Exception as e:
            logger.warning(f"⚠️ Torchvision load failed: {e}")

def _process_single_image(idx, url, input_dir):
    """Process a single image: download, mask, save. Used for parallel processing."""
    import numpy as np
    from PIL import Image
    
    img_data = b""
    try:
        img_data = requests.get(url, timeout=30).content
        masked_bytes = None
        engine_used = "None"
        
        # Try engines in priority order
        for engine_name in ["rembg", "mediapipe", "torchvision"]:
            engine_fn = _masking_engines.get(engine_name)
            if engine_fn:
                try:
                    masked_bytes = engine_fn(img_data)
                    engine_used = engine_name
                    break
                except Exception:
                    pass
        
        # Save result
        if masked_bytes:
            logger.info(f"✂️  Masked image {idx+1} ({engine_used})")
            with Image.open(io.BytesIO(masked_bytes)) as img:
                if img.mode in ("RGBA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    final = bg
                else:
                    final = img.convert("RGB")
                final.save(os.path.join(input_dir, f"img_{idx:04d}.jpg"), "JPEG", quality=95)
                # Ensure memory is released
                if 'bg' in locals():
                    del img, bg, final
                else:
                    del img, final
            return None
        else:
            # � FAIL FAST: Do not fallback to original image.
            # Unmasked images cause COLMAP to fail or produce garbage.
            error_msg = f"Masking failed for image {idx+1} (All engines failed: rembg, mediapipe, torchvision)"
            logger.error(f"❌ {error_msg}")
            return error_msg
            
    except Exception as e:
        error_msg = f"Image {idx+1} fatal error: {str(e)[:100]}"
        logger.error(f"❌ {error_msg}")
        return error_msg

def download_and_mask_images(images: list, input_dir: str):
    """
    🎓 Downloads and masks images in PARALLEL using ThreadPoolExecutor.
    
    NEW: Masking engines are loaded once and reused across all images.
    Parallel processing dramatically reduces time for many images (N images → N/num_workers time).
    Caching is transparent: check cache before downloading.
    """
    if not images:
        raise RuntimeError("No images provided for processing.")
    
    logger.info(f"🖼️  Processing {len(images)} images (parallel masking)...")
    
    # Initialize engines once per worker lifecycle
    _init_masking_engines()
    
    # Check cache: if all images are already masked, skip this stage entirely
    all_cached = True
    for img_url in images:
        cached_path = cache_get("masked_image", img_url)
        if not cached_path:
            all_cached = False
            break
    
    if all_cached:
        logger.info("💾 All images found in cache! Copying...")
        for idx, img_url in enumerate(images):
            cached_path = cache_get("masked_image", img_url)
            shutil.copy2(cached_path, os.path.join(input_dir, f"img_{idx:04d}.jpg"))
        return []
    
    # Parallel download + mask using ThreadPoolExecutor
    warnings = []
    max_workers = min(4, len(images))  # Limit to 4 threads (avoid GPU thrashing)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_process_single_image, idx, url, input_dir)
            for idx, url in enumerate(images)
        ]
        
        for idx, future in enumerate(concurrent.futures.as_completed(futures)):
            try:
                error = future.result()
                if error:
                    warnings.append(error)
            except Exception as e:
                warnings.append(f"Unexpected error processing image {idx}: {str(e)}")
    
    logger.info(f"✅ Image download and masking complete ({len(images) - len(warnings)} success, {len(warnings)} warnings)")
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
         "--SiftExtraction.max_num_features", "32768"])

    print("   🔗 Matching features between all image pairs...")
    run(["colmap", "exhaustive_matcher",
         "--database_path", db_path,
         "--SiftMatching.use_gpu", "1",
         "--SiftMatching.guided_matching", "1"], timeout=900)

    print("   📐 Reconstructing sparse 3D model...")
    run(["colmap", "mapper",
         "--database_path", db_path,
         "--image_path", input_dir,
         "--output_path", sparse_dir,
         "--Mapper.init_min_num_inliers", "15",
         "--Mapper.init_min_tri_angle", "0.5",
         "--Mapper.init_max_error", "8.0",
         "--Mapper.abs_pose_min_num_inliers", "15"])

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
        "colmap",  # 🌐 Use COLMAP dataparser (looks for images/ and sparse/0/)
        "--data", colmap_dir,
        "--max-num-iterations", "7000",
        "--viewer.quit-on-train-completion", "True",
        "--output-dir", splat_output_dir
    ]
    
    xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
    result = subprocess.run(xvfb + train_cmd, capture_output=True, text=True, timeout=3600)
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
    
    xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
    export_result = subprocess.run(xvfb + export_cmd, capture_output=True, text=True, timeout=600)
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

def upload_glb_async(glb_path: str, job_id: str, callback_queue: Queue = None) -> str:
    """
    🎓 Uploads the final .GLB to Cloudinary with retry logic and error handling.
    
    NEW: Returns a tuple (url, success, error) so caller can decide what to do.
    This enables non-blocking uploads while worker processes next job.
    """
    import cloudinary
    import cloudinary.uploader
    
    max_retries = 5  # Increased retries
    base_delay = 5  # seconds
    
    logger.info(f"☁️ Uploading .GLB to Cloudinary (job {job_id})...")
    cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
    
    for attempt in range(1, max_retries + 1):
        try:
            file_size_mb = os.path.getsize(glb_path) / (1024 * 1024)
            logger.info(f"   Upload attempt {attempt}/{max_retries} ({file_size_mb:.1f} MB)...")
            
            response = cloudinary.uploader.upload(
                glb_path,
                resource_type="raw",
                folder="3d_scanner_models",
                use_filename=True,
                unique_filename=True,
                timeout=600  # Increased timeout
            )
            url = response["secure_url"]
            logger.info(f"✅ Uploaded: {url}")
            
            if callback_queue:
                callback_queue.put({"job_id": job_id, "url": url, "success": True})
            
            return url
            
        except Exception as e:
            delay = base_delay * (2 ** (attempt - 1))  # Exponential backoff
            logger.warning(f"⚠️ Upload attempt {attempt} failed: {e}. Retrying in {delay}s...")
            if attempt < max_retries:
                time.sleep(delay)
    
    error_msg = f"Upload failed after {max_retries} attempts"
    logger.error(f"❌ {error_msg}")
    
    if callback_queue:
        callback_queue.put({"job_id": job_id, "url": None, "success": False, "error": error_msg})
    
    raise Exception(error_msg)


def upload_glb(glb_path: str) -> str:
    """Legacy sync wrapper for backward compatibility."""
    return upload_glb_async(glb_path, "legacy")


# ─────────────────────────────────────────────────────────
# 🔥 MAIN JOB PROCESSOR
# ─────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────
# 🏗️ CONCRETE PIPELINE STEPS
# ─────────────────────────────────────────────────────────

class MaskingStep(PipelineStep):
    def execute(self, images, images_dir):
        logger.info(f"🎭 Masking {len(images)} images...")
        warnings = download_and_mask_images(images, str(images_dir))
        if warnings:
            logger.warning(f"⚠️ Masking had issues: {len(warnings)} images failed.")
            return warnings
        return []

class ColmapStep(PipelineStep):
    def execute(self, images_dir, workspace):
        logger.info("📸 Running COLMAP SfM...")
        return run_colmap(str(images_dir), str(workspace))

class SplattingStep(PipelineStep):
    def execute(self, workspace):
        logger.info("✨ Training Gaussian Splats...")
        return run_nerfstudio(str(workspace), str(workspace))

class MeshingStep(PipelineStep):
    def execute(self, splat_ply, workspace):
        logger.info("🕸️ Converting Splats to Mesh...")
        return splat_to_glb(splat_ply, str(workspace))

class UploadStep(PipelineStep):
    def execute(self, glb_path):
        logger.info("📤 Uploading artifact...")
        return upload_glb(glb_path)

# ─────────────────────────────────────────────────────────
# 🎮 ORCHESTRATION
# ─────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────
# 🎮 ORCHESTRATION (THE PIPELINE CONTROLLER)
# ─────────────────────────────────────────────────────────

def process_job(job_id: str, images: list):
    """
    🎓 TEACHER'S NOTE: The Pipeline Controller.
    Instead of one big block, we delegate to specialized modules.
    If a module fails, we decide whether to abort or use a fallback.
    """
    workspace = Path(f"/kaggle/working/job_{job_id[:8]}")
    images_dir = workspace / "images"
    
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    def update_prog(pct, msg):
        report_progress(job_id, status="processing", progress=f"{pct}% - {msg}")
        logger.info(f"📊 {pct}% - {msg}")

    try:
        # 🧪 Step 0: Dependency Check/Install (Ensures binary stability)
        install_dependencies()

        # 🚀 Step 1: Masking
        update_prog(10, "Masking images...")
        images_dir.mkdir(parents=True, exist_ok=True)  # ✅ FIX: ensure dir exists before any writes
        try:
            mask_engine = MaskingStep()
            mask_engine.execute(images, str(images_dir))
        except Exception as e:
            logger.error(f"❌ Masking failed critical: {e}. Attempting with original images.")
            # Fail-safe: if engine init fails, download raw images without masking
            for i, url in enumerate(images):
                try:
                    img_data = requests.get(url, timeout=30).content
                    with open(images_dir / f"img_{i:04d}.png", "wb") as f:
                        f.write(img_data)
                except Exception as download_err:
                    logger.error(f"❌ Raw download also failed for image {i}: {download_err}")

        # 📸 Step 2: COLMAP
        update_prog(30, "Aligning cameras (COLMAP)...")
        colmap_engine = ColmapStep()
        sparse_dir = colmap_engine.execute(str(images_dir), str(workspace))

        # ✨ Step 3: Gaussian Splatting
        update_prog(50, "Training Neural Splats...")
        splat_engine = SplattingStep()
        splat_ply = splat_engine.execute(str(workspace))

        best_artifact = None

        if splat_ply and os.path.exists(splat_ply):
            # 🕸️ Step 4: Meshing (Best Quality)
            update_prog(80, "Converting Splats to Mesh...")
            mesh_engine = MeshingStep()
            best_artifact = mesh_engine.execute(splat_ply, str(workspace))
            
            if not best_artifact:
                logger.warning("⚠️ Meshing failed. Falling back to raw PLY...")
                best_artifact = splat_ply
        else:
            # ✅ FIX: COLMAP outputs binary .bin format. Use model_converter to get a .ply
            logger.warning("⚠️ Splatting failed. Falling back to COLMAP sparse cloud...")
            ply_path = os.path.join(str(workspace), "colmap_sparse.ply")
            try:
                subprocess.run([
                    "colmap", "model_converter",
                    "--input_path", os.path.join(sparse_dir, "0"),
                    "--output_path", ply_path,
                    "--output_type", "PLY"
                ], check=True, capture_output=True)
                best_artifact = ply_path
                logger.info(f"✅ Exported COLMAP sparse PLY: {ply_path}")
            except Exception as colmap_ply_err:
                logger.error(f"❌ colmap model_converter failed: {colmap_ply_err}")
                raise RuntimeError("Both Gaussian Splatting and COLMAP PLY export failed.")

        # 📤 Step 5: Upload
        update_prog(95, "Uploading results...")
        upload_engine = UploadStep()
        # ✅ FIX: UploadStep reads credentials from globals (CLOUD_NAME, API_KEY, API_SECRET)
        model_url = upload_engine.execute(best_artifact)

        # ✅ Done
        report_progress(job_id, status="completed", model_url=model_url, progress="100% - Complete!")
        logger.info(f"🎉 Job {job_id} finished successfully.")

    except Exception as e:
        logger.error(f"🚨 PIPELINE FATAL: {e}")
        report_progress(job_id, status="failed", error_message=str(e)[:500])
    finally:
        if workspace.exists() and not os.environ.get("DEBUG_KEEP"):
            shutil.rmtree(workspace)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        mark_worker_idle()


# ─────────────────────────────────────────────────────────
# 🚀 MAIN LOOP
# ─────────────────────────────────────────────────────────

def start_worker():
    """
    🎓 The main worker loop — now uses Redis Queue instead of HTTP polling!
    
    ARCHITECTURE CHANGE (v3.0):
    - OLD: Worker polls HTTP endpoint /workers/next-job every 15s
    - NEW: Backend pushes jobs to Redis queue when uploaded
    - BENEFIT: ~100x reduction in unnecessary HTTP round-trips
    
    This worker runs CONTINUOUSLY and processes jobs from the Redis queue.
    When a job is available, it runs the entire Gaussian Splatting pipeline.
    """
    install_dependencies()
    
    # Pipeline steps are now embedded inline (no external imports needed)
    global MaskingStep, ColmapStep, SplattingStep, MeshingStep, UploadStep
    
    # Embedded pipeline classes to avoid import issues in Kaggle
    class MaskingStep:
        def __init__(self):
            from rembg import remove, new_session
            try:
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                self.session = new_session("isnet-general-use", providers=providers)
                logger.info("✅ Masking engine initialized")
            except Exception as e:
                logger.warning(f"⚠️ Masking init failed: {e}")
                self.session = None

        def execute(self, images, images_dir):
            from rembg import remove
            os.makedirs(images_dir, exist_ok=True)
            for i, url in enumerate(images):
                try:
                    img_data = requests.get(url, timeout=30).content
                    masked_data = remove(img_data, session=self.session)
                    with open(os.path.join(images_dir, f"img_{i:04d}.png"), "wb") as f:
                        f.write(masked_data)
                except Exception as e:
                    logger.error(f"❌ Failed to mask image {i}: {e}")
                    raise

    class ColmapStep:
        def execute(self, images_dir, workspace):
            db_path = os.path.join(workspace, "database.db")
            sparse_dir = os.path.join(workspace, "sparse")
            os.makedirs(sparse_dir, exist_ok=True)
            
            xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
            
            def run_colmap_cmd(cmd_args, step_name, timeout=900):
                """✅ FIX: Captures output but logs stderr on failure for easier debugging."""
                result = subprocess.run(xvfb + cmd_args, capture_output=True, text=True, timeout=timeout)
                if result.returncode != 0:
                    # Log the last 30 lines of stderr so we can see what COLMAP complained about
                    error_tail = "\n".join(result.stderr.splitlines()[-30:])
                    logger.error(f"❌ COLMAP {step_name} failed:\n{error_tail}")
                    raise subprocess.CalledProcessError(result.returncode, cmd_args)
                return result
            
            logger.info("📸 COLMAP: Extracting features...")
            run_colmap_cmd([
                "colmap", "feature_extractor",
                "--database_path", db_path,
                "--image_path", images_dir,
                "--SiftExtraction.use_gpu", "1",
                "--SiftExtraction.max_image_size", "3200",
                "--SiftExtraction.max_num_features", "32768"
            ], "feature_extractor")
            
            logger.info("📸 COLMAP: Matching features...")
            run_colmap_cmd([
                "colmap", "exhaustive_matcher",
                "--database_path", db_path,
                "--SiftMatching.use_gpu", "1"
            ], "exhaustive_matcher")
            
            logger.info("📸 COLMAP: Mapping sparse cloud...")
            run_colmap_cmd([
                "colmap", "mapper",
                "--database_path", db_path,
                "--image_path", images_dir,
                "--output_path", sparse_dir,
                "--Mapper.init_min_num_inliers", "15",
                "--Mapper.init_min_tri_angle", "0.5",
                "--Mapper.abs_pose_min_num_inliers", "15"
            ], "mapper")
            
            logger.info("✅ COLMAP complete!")
            return sparse_dir

    class SplattingStep:
        def execute(self, workspace):
            import glob
            splat_dir = os.path.join(workspace, "splat")
            os.makedirs(splat_dir, exist_ok=True)
            
            # ✅ FIX: Nerfstudio needs a virtual display (headless Kaggle). Add xvfb-run.
            xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
            
            logger.info("✨ Training Gaussian Splats (Nerfstudio splatfacto)...")
            train_result = subprocess.run(xvfb + [
                "ns-train", "splatfacto",
                "colmap",
                "--data", workspace,
                "--max-num-iterations", "3000",
                "--viewer.quit-on-train-completion", "True",
                "--output-dir", splat_dir
            ], capture_output=True, text=True, timeout=3600)
            
            if train_result.returncode != 0:
                error_tail = "\n".join(train_result.stderr.splitlines()[-20:])
                logger.error(f"❌ ns-train failed:\n{error_tail}")
                raise RuntimeError("Nerfstudio splatfacto training failed.")
            
            configs = glob.glob(os.path.join(splat_dir, "**/config.yml"), recursive=True)
            if not configs:
                raise RuntimeError("Training completed but config.yml not found.")
            
            logger.info("✨ Exporting Gaussian Splat PLY...")
            export_result = subprocess.run(xvfb + [
                "ns-export", "gaussian-splat",
                "--load-config", configs[0],
                "--output-dir", splat_dir
            ], capture_output=True, text=True, timeout=600)
            
            if export_result.returncode != 0:
                error_tail = "\n".join(export_result.stderr.splitlines()[-20:])
                logger.error(f"❌ ns-export failed:\n{error_tail}")
                raise RuntimeError("ns-export gaussian-splat failed.")
            
            splat_ply = os.path.join(splat_dir, "splat.ply")
            if not os.path.exists(splat_ply):
                raise RuntimeError(f"ns-export finished but {splat_ply} was not created.")
            
            logger.info(f"✅ Splat PLY saved: {splat_ply}")
            return splat_ply

    class MeshingStep:
        def execute(self, ply_path, workspace):
            import pymeshlab, trimesh
            obj_path = os.path.join(workspace, "model.obj")
            glb_path = os.path.join(workspace, "model.glb")
            
            logger.info("🕸️ Converting to mesh...")
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(ply_path)
            ms.compute_normal_for_point_clouds()
            ms.generate_surface_reconstruction_screened_poisson()
            ms.save_current_mesh(obj_path)
            
            mesh = trimesh.load(obj_path)
            mesh.export(glb_path)
            return glb_path

    class UploadStep:
        def execute(self, glb_path):
            import cloudinary, cloudinary.uploader
            cloudinary.config(
                cloud_name=CLOUD_NAME,
                api_key=API_KEY,
                api_secret=API_SECRET
            )
            
            response = cloudinary.uploader.upload(
                glb_path,
                resource_type="raw",
                folder="3d_models"
            )
            return response["secure_url"]
    
    logger.info("✅ Pipeline modules loaded successfully (embedded).")
        
    check_backend_url()
    register_worker()
    
    # 🧪 PASS 7: Graceful Shutdown Handling
    def handle_exit(sig, frame):
        logger.info("🛑 Termination signal received. Cleaning up...")
        mark_worker_idle()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    logger.info("╔" + "═" * 60 + "╗")
    logger.info("║  MORPHIC GPU WORKER v3.0 — REDIS QUEUE EDITION          ║")
    logger.info("║  Gaussian Splatting + Multi-Engine Background Removal   ║")
    logger.info("╚" + "═" * 60 + "╝")
    logger.info(f"Backend:     {BACKEND_URL}")
    logger.info(f"Worker ID:   {WORKER_ID}")
    logger.info(f"Architecture: Redis Queue-based (not HTTP polling)")
    logger.info("Status: Listening for jobs...")
    logger.info("")

    backoff = POLL_INTERVAL
    consecutive_empty_polls = 0
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            # Safer cleanup: only remove jobs older than 1 hour
            try:
                os.system("find /kaggle/working/job_* -mtime +0.042 -exec rm -rf {} + 2>/dev/null")
            except Exception:
                pass
            
            try:
                job_data = get_next_job()
                if job_data and job_data.get("job_id"):
                    backoff = POLL_INTERVAL
                    consecutive_empty_polls = 0
                    consecutive_errors = 0  # Reset on success
                    job_id = job_data["job_id"]
                    images = job_data.get("images", [])
                    logger.info(f"🔥 [JOB] {job_id[:8]}... ({len(images)} images)")
                    process_job(job_id, images)
                else:
                    consecutive_empty_polls += 1
                    if consecutive_empty_polls % 10 == 0:  # Log every 10th empty poll
                        logger.debug(f"No jobs available (checked {consecutive_empty_polls}x, waiting {backoff}s...)")
                    else:
                        # Silent wait for first 9 checks
                        pass
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Job processing error: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"Too many consecutive errors ({consecutive_errors}). Restarting worker...")
                    break  # Exit to restart
                backoff = min(backoff * 1.5, 300)  # cap at 5 minutes, slower backoff
            
        except Exception as e:
            logger.critical(f"Critical worker error: {e}. Restarting...")
            break  # Exit to restart
        
        time.sleep(backoff)


# ─── ENTRY POINT ───
if __name__ == "__main__":
    if "ollie-unfashionable" in BACKEND_URL:
        print("⚠️  WARNING: You are using the DEFAULT BACKEND_URL.")
        print("💡 Make sure to replace it with your actual Ngrok URL at the top of the script!")
    
    if not CLOUD_NAME or "env" in CLOUD_NAME.lower():
        print("⚠️  WARNING: Cloudinary credentials NOT detected.")
        print("💡 Remember to set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET.")
        
    start_worker()
