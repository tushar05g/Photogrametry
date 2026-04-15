#!/usr/bin/env python3
"""
⚡ QUICK START - Backend + 3D Model Generation
Starts backend server and runs local model generation tests
Usage: python start_and_test.py
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
VENV_PATH = PROJECT_ROOT / "venv"

def start_backend():
    """Start the FastAPI backend server"""
    print("\n" + "="*70)
    print("🚀 STARTING BACKEND SERVER")
    print("="*70)
    
    # Determine Python executable
    if sys.platform == "win32":
        python_exe = VENV_PATH / "Scripts" / "python.exe"
    else:
        python_exe = VENV_PATH / "bin" / "python"
    
    if not python_exe.exists():
        print(f"❌ Python executable not found at {python_exe}")
        print("Please ensure venv is configured correctly")
        return None
    
    # Start backend in subprocess
    print(f"Starting: {python_exe} -m uvicorn backend.main:app --reload")
    
    try:
        process = subprocess.Popen(
            [str(python_exe), "-m", "uvicorn", "backend.main:app", "--reload"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("✅ Backend process started")
        
        # Wait for server to be ready
        print("\n⏳ Waiting for backend to be ready (checking http://localhost:8000)...")
        
        import requests
        for i in range(60):  # 60 tries, 1 second each = 60 seconds max
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print("✅ Backend is ready and responding")
                    return process
            except:
                pass
            
            time.sleep(1)
            print(".", end="", flush=True)
        
        # If we get here, server didn't start properly
        print("\n❌ Backend did not start properly")
        process.terminate()
        return None
        
    except Exception as e:
        print(f"❌ Error starting backend: {e}")
        return None

def run_tests():
    """Run the local 3D model generation tests"""
    print("\n" + "="*70)
    print("🧪 RUNNING LOCAL 3D MODEL GENERATION TESTS")
    print("="*70)
    
    # Determine Python executable
    if sys.platform == "win32":
        python_exe = VENV_PATH / "Scripts" / "python.exe"
    else:
        python_exe = VENV_PATH / "bin" / "python"
    
    try:
        result = subprocess.run(
            [str(python_exe), "test_local_3d_generation.py"],
            cwd=str(PROJECT_ROOT),
            timeout=3600  # 1 hour timeout
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Tests timed out after 1 hour")
        return False
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main execution"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                  ⚡ BACKEND + 3D MODEL GENERATION ⚡                        ║
║         Start Backend Server and Generate 3D Models from Assets            ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check environment
    print("\n📋 PRE-FLIGHT CHECKS")
    print("-" * 70)
    
    if not PROJECT_ROOT.exists():
        print(f"❌ Project root not found: {PROJECT_ROOT}")
        sys.exit(1)
    print(f"✅ Project root: {PROJECT_ROOT}")
    
    if not (PROJECT_ROOT / "backend" / "main.py").exists():
        print(f"❌ Backend main.py not found")
        sys.exit(1)
    print(f"✅ Backend code found")
    
    if not VENV_PATH.exists():
        print(f"❌ venv not found at {VENV_PATH}")
        print("Please create venv first: python -m venv venv")
        sys.exit(1)
    print(f"✅ venv found")
    
    assets_dir = PROJECT_ROOT / "assets"
    turtle_dir = assets_dir / "turtle_images"
    cube_dir = assets_dir / "cube_images"
    
    if not turtle_dir.exists():
        print(f"⚠️  Turtle images not found: {turtle_dir}")
    else:
        turtle_count = len(list(turtle_dir.glob("*.png")))
        print(f"✅ Turtle images: {turtle_count} files")
    
    if not cube_dir.exists():
        print(f"⚠️  Cube images not found: {cube_dir}")
    else:
        cube_count = len(list(cube_dir.glob("*.png")))
        print(f"✅ Cube images: {cube_count} files")
    
    # Start backend
    backend_process = start_backend()
    if not backend_process:
        print("\n❌ Failed to start backend. Cannot proceed.")
        sys.exit(1)
    
    try:
        # Run tests
        success = run_tests()
        
        if success:
            print("\n" + "="*70)
            print("🎉 ALL TESTS COMPLETED SUCCESSFULLY")
            print("="*70)
            output_dir = PROJECT_ROOT / "output" / "3d_models"
            print(f"\n📁 Models saved to: {output_dir}")
        else:
            print("\n⚠️  Tests completed with issues")
    
    finally:
        # Cleanup
        print("\n" + "="*70)
        print("🛑 SHUTTING DOWN BACKEND")
        print("="*70)
        backend_process.terminate()
        try:
            backend_process.wait(timeout=5)
            print("✅ Backend shut down cleanly")
        except subprocess.TimeoutExpired:
            backend_process.kill()
            print("⚠️  Backend force terminated")

if __name__ == "__main__":
    main()
