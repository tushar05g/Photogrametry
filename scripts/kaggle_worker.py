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
    """Checks for COLMAP and XVFB."""
    print("📋 Checking for COLMAP & XVFB...")
    try:
        subprocess.run(["colmap", "-h"], capture_output=True)
        subprocess.run(["xvfb-run", "--help"], capture_output=True)
        print("✅ System dependencies are ready!")
    except (FileNotFoundError, ImportError):
        print("⚙️ Installing GPU Tools (COLMAP + XVFB + Cloudinary)...")
        os.system("apt-get update -qq && apt-get install -y -qq colmap xvfb")
        os.system("pip install -q cloudinary")

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
        subprocess.check_call(full_cmd)
    except subprocess.CalledProcessError as e:
        print(f"❌ COLMAP Command Failed: {e}")
        # Fallback to CPU if GPU still fails (Safety First)
        if use_gpu:
            print("⚠️ GPU Failed! Retrying on CPU (this will be slower)...")
            cpu_args = [a for a in args if "use_gpu" not in a]
            cpu_args.extend(["--SiftExtraction.use_gpu", "0", "--SiftMatching.use_gpu", "0"])
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
    if os.path.exists("input_images"): shutil.rmtree("input_images")
    if os.path.exists("output"): shutil.rmtree("output")
    os.makedirs("input_images", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    db_path = "database.db"
    if os.path.exists(db_path): os.remove(db_path)

    # 3. Download
    for i, url in enumerate(images):
        img_data = requests.get(url).content
        filename = f"input_images/img_{i:03d}.jpg"
        with open(filename, 'wb') as f: f.write(img_data)
        print(f"   📥 Downloaded {i+1}/{len(images)}")

    # 4. Update PC status
    requests.patch(f"{NGROK_URL}/scans/{job_id}", json={"status": "processing"})

    try:
        if not check_job_status(job_id): return
        print("🧠 [STAGE 1] Extracting Features (GPU)...")
        run_colmap_command([
            "colmap", "feature_extractor", 
            "--database_path", db_path, 
            "--image_path", "input_images",
            "--SiftExtraction.use_gpu", "1",     # 🔥 ENABLE GPU
            "--SiftExtraction.max_image_size", "2400" # High-quality processing
        ])

        if not check_job_status(job_id): return
        print("🔗 [STAGE 2] Matching Features (GPU)...")
        run_colmap_command([
            "colmap", "exhaustive_matcher", 
            "--database_path", db_path,
            "--SiftMatching.use_gpu", "1"      # 🔥 ENABLE GPU
        ])

        if not check_job_status(job_id): return
        print("🏗️ [STAGE 3] Building 3D Structure...")
        # Mapper doesn't use OpenGL, so standard run is fine
        run_colmap_command([
            "colmap", "mapper", 
            "--database_path", db_path, 
            "--image_path", "input_images", 
            "--output_path", "output"
        ], use_gpu=False)

        # Check if reconstruction worked - find the first folder with a model
        subdirs = [d for d in os.listdir("output") if os.path.isdir(os.path.join("output", d))]
        if not subdirs:
            raise Exception("COLMAP failed to triangulate any points. Try taking more overlapping photos!")
        
        # Usually '0', but could be others if multiple trials happened
        model_dir = os.path.join("output", sorted(subdirs)[0])
        print(f"📍 Using reconstruction from: {model_dir}")

        if not check_job_status(job_id): return

        print("📦 [STAGE 4] Converting to .PLY Mesh...")
        result_file = "output/model.ply"
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
