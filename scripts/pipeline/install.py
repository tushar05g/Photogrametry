import os
import subprocess
import sys
import importlib.metadata
import logging

logger = logging.getLogger(__name__)

def verify_versions():
    """Verify package versions without importing them (prevents locking memory)."""
    required = {
        "numpy": "1.26.4",
        "Pillow": "10.3.0",
        "torchvision": "0.17.2"
    }
    
    for pkg, version in required.items():
        try:
            installed = importlib.metadata.version(pkg)
            if installed != version:
                logger.warning(f"⚠️ {pkg} version mismatch: found {installed}, need {version}")
                return False
        except importlib.metadata.PackageNotFoundError:
            logger.warning(f"⚠️ {pkg} not found.")
            return False
    return True

def install_core_deps():
    """
    Atomic installation of core reconstruction dependencies.
    Streams output so user can see progress.
    """
    cmd = [
        sys.executable, "-m", "pip", "install",
        "numpy==1.26.4",
        "Pillow==10.3.0",
        "torchvision==0.17.2",
        "rembg==2.0.60",
        "onnxruntime-gpu",
        "mediapipe",
        "nerfstudio",
        "gsplat",
        "trimesh",
        "pymeshlab",
        "cloudinary",
        "--upgrade",
        "--no-cache-dir",
        "--break-system-packages"
    ]
    
    logger.info("⚙️ Running atomic dependency installation (streaming output)...")
    try:
        # ✅ FIXED: Removed capture_output=True to allow streaming to console
        subprocess.run(cmd, check=True)
        
        logger.info("✅ Installation complete.")
        print("\n" + "!" * 60)
        print("🚨 RESTART REQUIRED")
        print("Dependencies have been updated. To avoid binary mismatch errors,")
        print("please RESTART the cell or the Kaggle Session now.")
        print("!" * 60 + "\n")
        
        # In a worker script, we can attempt an auto-restart
        is_notebook = 'ipykernel' in sys.modules or any("ipykernel" in arg for arg in sys.argv)
        
        if not is_notebook:
             logger.info("🔄 Auto-restarting worker process...")
             os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
             logger.info("👋 Installation complete. Please restart this cell to finish setup.")
             sys.exit(0)
             
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Dependency installation failed.")
        raise e

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if not verify_versions():
        install_core_deps()
    else:
        logger.info("✅ All core dependencies are correct.")
