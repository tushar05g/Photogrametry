import os
import requests
import time
import subprocess
import shutil

# ---------------------------------------------------------
# MORPHIC PRO-WORKER (HEADLESS GPU ACCELERATED)
# ---------------------------------------------------------
# This script runs on your Kaggle GPU Notebook.
# It uses XVFB to trick COLMAP into using the GPU without a monitor.
# ---------------------------------------------------------

# 🔧 CONFIGURATION
NGROK_URL = "https://ollie-unfashionable-topographically.ngrok-free.dev"
POLL_INTERVAL = 15 # Seconds

# ☁️ CLOUDINARY SECRETS
CLOUD_NAME = "dbvidngtc"
API_KEY = "965528154675166"
API_SECRET = "VimOI9Zi1dPIyc7x0rzC_JChl8I"

# 🔥 HEADLESS FIX: We'll use xvfb-run instead of just environment variables
# This allows the GPU (OpenGL) to initialize without a real monitor.

def install_dependencies():
    """Checks for COLMAP, XVFB, and Python packages."""
    print("📋 Checking for COLMAP & XVFB & Python Packages...")
    try:
        # 🏎️ TURBO BOOT: Only install if core libraries are missing
        import cloudinary
        import rembg
        import cv2 # opencv-python-headless
        print("✅ System dependencies are already cached and ready!")
    except (FileNotFoundError, ImportError):
        print("⚙️ Installing GPU Tools (COLMAP + XVFB + Cloudinary + Rembg)...")
        os.system("apt-get update -qq && apt-get install -y -qq colmap xvfb")
        # Consolidated install to prevent fighting between pip calls
        # 1. Force remove any GUI-enabled OpenCV or conflicting ONNX runtimes
        print("📦 Synchronizing Python Stack (this may take a minute)...")
        os.system("python3 -m pip uninstall -y -q opencv-python opencv-contrib-python opencv-python-headless onnxruntime")
        os.system("python3 -m pip install -q --no-warn-conflicts 'numpy>=2.0' 'onnxruntime-gpu' 'rembg' 'cloudinary' 'pillow<10.1.0' 'protobuf' 'opencv-python-headless'")

def upload_to_cloudinary(file_path):
    """Uploads the final 3D file to your Cloudinary account."""
    print(f"☁️ Uploading {file_path} to Cloudinary...")
    try:
        import cloudinary.uploader
        cloudinary.config(cloud_name=CLOUD_NAME, api_key=API_KEY, api_secret=API_SECRET)
        response = cloudinary.uploader.upload(file_path, resource_type="raw", folder="3d_scanner_models")
        return response['secure_url']
    except Exception as e:
        print(f"❌ Cloudinary Upload Error: {e}")
        return None

def run_colmap_command(args, use_gpu=True):
    """Executes a COLMAP command, wrapping in xvfb-run only if using GPU."""
    if use_gpu:
        # We wrap the command in xvfb-run -a to create a virtual display for OpenGL
        xvfb_prefix = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
        full_cmd = xvfb_prefix + args
        print(f"🛠️ Executing GPU-Accelerated: {' '.join(args)}")
    else:
        full_cmd = args
        print(f"🛠️ Executing: {' '.join(args)}")
    
    try:
        # 🛡️ RESILIENCE: Added a 10-minute timeout to prevent jobs from hanging indefinitely
        subprocess.check_call(full_cmd, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"⏰ COLMAP Command Timed Out after 10 mins: {' '.join(args)}")
        raise Exception("Reconstruction took too long. Try uploading fewer or smaller images.")
    except subprocess.CalledProcessError as e:
        print(f"❌ COLMAP Command Failed: {e}")
        # Fallback to CPU if GPU still fails (Safety First)
        if use_gpu:
            print("⚠️ GPU Failed! Retrying on CPU (this will be slower)...")
            
            # Robustly filter out GPU-related arguments and their values
            cpu_args = []
            skip_next = False
            for i, arg in enumerate(args):
                if skip_next:
                    skip_next = False
                    continue
                if "use_gpu" in arg:
                    skip_next = True # Skip the value (0 or 1) that follows
                    continue
                cpu_args.append(arg)
            
            # Add the correct CPU flag based on the command type
            if "feature_extractor" in args:
                cpu_args.extend(["--SiftExtraction.use_gpu", "0"])
            elif "exhaustive_matcher" in args:
                cpu_args.extend(["--SiftMatching.use_gpu", "0"])
            
            subprocess.check_call(cpu_args)
        else:
            raise e

def check_job_status(job_id):
    """Checks if the job is still active on the server."""
    try:
        r = requests.get(f"{NGROK_URL}/scans/{job_id}", timeout=10)
        if r.status_code == 200:
            status = r.json().get("status")
            if status in ["failed", "cancelled"]:
                print(f"🛑 Job {job_id} was marked as '{status}' on server. Stopping worker.")
                return False
        return True
    except Exception as e:
        print(f"⚠️ Status check failed: {e}")
        return True # Continue if network transient error

def process_job(job_id):
    print(f"\n🔥 [REAL-TIME] Starting GPU 3D Scan for Job: {job_id}")
    
    # 1. Fetch Images
    try:
        response = requests.get(f"{NGROK_URL}/scans/{job_id}/images")
        response.raise_for_status()
        images = response.json()["images"]
    except Exception as e:
        print(f"❌ Server Error: {e}")
        return

    # 2. Workspace Prep
    job_dir = f"job_{job_id}"
    input_dir = os.path.join(job_dir, "input")
    output_dir = os.path.join(job_dir, "output")
    db_path = os.path.join(job_dir, "database.db")

    if os.path.exists(job_dir): shutil.rmtree(job_dir)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # 3. Download & Segregate Object (rembg)
    print("✂️ [STAGE 0] Removing Backgrounds (Object Segregation)...")
    rembg_remove = None
    try:
        from rembg import remove as _rembg_remove
        rembg_remove = _rembg_remove
        from PIL import Image
        import io
    except ImportError as e:
        print(f"⚠️ rembg import failed: {e}")

    job_warnings = []
    remove_bg = True # ✂️ Set to False if you want to skip masking

    for i, url in enumerate(images):
        if i % 5 == 0 and not check_job_status(job_id): return
        img_data = requests.get(url).content
        filename = os.path.join(input_dir, f"img_{i:03d}.jpg")
        
        # Apply Background Removal if requested and available
        if remove_bg and rembg_remove:
            try:
                # 🛠️ BYPASS PIL: Pass bytes directly to rembg to avoid 'mode' setter errors
                output_data = rembg_remove(img_data)
                
                # Convert result to high-quality JPEG
                with Image.open(io.BytesIO(output_data)) as masked_img:
                    # Ensure it's RGB (force white background if it was transparent)
                    if masked_img.mode in ("RGBA", "P"):
                        background = Image.new("RGB", masked_img.size, (255, 255, 255))
                        background.paste(masked_img, mask=masked_img.split()[3]) # 3 is alpha
                        final_save = background
                    else:
                        final_save = masked_img.convert("RGB")
                    
                    final_save.save(filename, "JPEG", quality=95)
                
                print(f"   ✂️ Masked & Saved {i+1}/{len(images)}")
            except Exception as e:
                warn_msg = f"Masking failed for image {i+1}: {str(e)[:100]}"
                print(f"   ⚠️ {warn_msg}")
                job_warnings.append(warn_msg)
                with open(filename, 'wb') as f: f.write(img_data)
        else:
            with open(filename, 'wb') as f: f.write(img_data)
            print(f"   📥 Downloaded {i+1}/{len(images)}")

    # 💡 Memory Cleanup: Force remove rembg from GPU before COLMAP starts
    if remove_bg and rembg_remove:
        # 🛡️ Report warnings back to server so user knows the model might be imperfect
        if job_warnings:
            requests.patch(f"{NGROK_URL}/scans/{job_id}", json={
                "warnings": " | ".join(job_warnings)
            })
            
        # Clear memory
        del rembg_remove
        import gc
        gc.collect()
        print("🧱 Snapshot: GPU Memory purge complete.")

    # 4. Update PC status
    requests.patch(f"{NGROK_URL}/scans/{job_id}", json={"status": "processing"})

    try:
        if not check_job_status(job_id): return
        print("🧠 [STAGE 1] Extracting Features (GPU)...")
        run_colmap_command([
            "colmap", "feature_extractor", 
            "--database_path", db_path, 
            "--image_path", input_dir,
            "--SiftExtraction.use_gpu", "1",
            "--SiftExtraction.max_image_size", "2400",
            "--SiftExtraction.max_num_features", "16384",
            "--SiftExtraction.estimate_affine_shape", "1"
        ])

        if not check_job_status(job_id): return
        print("🔗 [STAGE 2] Matching Features (GPU)...")
        run_colmap_command([
            "colmap", "exhaustive_matcher", 
            "--database_path", db_path,
            "--SiftMatching.use_gpu", "1",
            "--SiftMatching.max_num_matches", "32768"
        ])

        if not check_job_status(job_id): return
        print("🏗️ [STAGE 3] Building 3D Structure...")
        run_colmap_command([
            "colmap", "mapper", 
            "--database_path", db_path, 
            "--image_path", input_dir, 
            "--output_path", output_dir
        ], use_gpu=False)

        # Check if reconstruction worked
        subdirs = [d for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        if not subdirs:
            raise Exception("COLMAP failed to triangulate any points. Try taking more overlapping photos!")
        
        model_dir = os.path.join(output_dir, sorted(subdirs)[0])
        print(f"📍 Using reconstruction from: {model_dir}")

        if not check_job_status(job_id): return

        print("📦 [STAGE 4] Converting to .PLY Mesh...")
        result_file = os.path.join(output_dir, "model.ply")
        run_colmap_command([
            "colmap", "model_converter", 
            "--input_path", model_dir, 
            "--output_path", result_file, 
            "--output_type", "PLY"
        ], use_gpu=False)

        # 6. Upload Result
        if os.path.exists(result_file):
            print("✅ Success! 3D File Generated.")
            final_url = upload_to_cloudinary(result_file)
            
            if final_url:
                requests.patch(f"{NGROK_URL}/scans/{job_id}", json={
                    "status": "completed",
                    "model_url": final_url
                })
                print(f"🎉 MISSION COMPLETE! Model: {final_url}")
                # Cleanup
                shutil.rmtree(job_dir)
            else:
                raise Exception("Cloudinary upload failed.")
        else:
            raise Exception("Conversion to PLY failed.")

    except Exception as e:
        print(f"💥 Processing error: {e}")
        requests.patch(f"{NGROK_URL}/scans/{job_id}", json={
            "status": "failed",
            "error_message": str(e)
        })
        if os.path.exists(job_dir): shutil.rmtree(job_dir)

def start_polling():
    install_dependencies()
    print(f"\n📡 MORPHIC AUTO-WORKER IS READY (GPU-VIRTUAL)")
    print("---------------------------------------")
    while True:
        try:
            response = requests.get(f"{NGROK_URL}/scans/next-pending")
            if response.status_code == 200:
                process_job(response.json()["id"])
        except Exception as e: print(f"🌐 Waiting for PC... ({e})")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    start_polling()
