#!/usr/bin/env python3
"""
🐢 LOCAL TESTING SCRIPT - Generate 3D Models from Assets
Simulates the Kaggle workflow for local testing
Creates 3D models from turtle and cube images
"""

import os
import sys
import time
import requests
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path
sys.path.insert(0, os.getcwd())

# Configuration
BASE_URL = "http://localhost:8000"
API_V1 = f"{BASE_URL}/api/v1"
PROJECT_ROOT = Path(__file__).parent
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTPUT_DIR = PROJECT_ROOT / "output" / "3d_models"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class LocalPipelineTester:
    """Test the photogrammetry pipeline using local assets"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v1"
        self.completed_jobs = []
        
    def check_backend(self) -> bool:
        """Verify backend is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Backend is online")
                return True
        except Exception as e:
            print(f"❌ Backend offline: {e}")
            return False
        return False
    
    def upload_images(self, image_dir: Path, project_name: str, enable_splat: bool = False) -> Optional[str]:
        """Upload images and create job"""
        images = list(image_dir.glob("*.png"))
        
        if not images:
            print(f"❌ No PNG images found in {image_dir}")
            return None
        
        print(f"📤 Uploading {len(images)} images from {image_dir.name}...")
        
        # Prepare files
        files = [
            ("files", (img.name, open(img, "rb"), "image/png"))
            for img in sorted(images)
        ]
        
        # Upload
        try:
            response = requests.post(
                f"{self.api_url}/jobs/upload",
                files=files,
                data={
                    "project_name": project_name,
                    "enable_splat": "true" if enable_splat else "false"
                },
                timeout=300
            )
            
            # Close files
            for _, (_, file_obj, _) in files:
                if hasattr(file_obj, 'close'):
                    file_obj.close()
            
            if response.status_code == 200:
                job_data = response.json()
                job_id = job_data.get("job_id")
                print(f"✅ Job created: {job_id}")
                print(f"   Images: {len(images)}")
                print(f"   Project: {project_name}")
                return job_id
            else:
                print(f"❌ Upload failed: {response.status_code}")
                print(f"   {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return None
    
    def poll_job_status(self, job_id: str, timeout: int = 7200) -> bool:
        """Poll job status until completion"""
        print(f"\n⏳ Monitoring job {job_id}...")
        start_time = time.time()
        last_stage = None
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.api_url}/scans/{job_id}/progress",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "unknown")
                    stage = data.get("current_stage", "unknown")
                    progress = data.get("progress", 0)
                    
                    if stage != last_stage:
                        elapsed = int(time.time() - start_time)
                        print(f"   [{elapsed}s] {stage} ({progress}%)")
                        last_stage = stage
                    
                    if status == "completed":
                        print(f"\n🎉 Job completed successfully in {int(time.time() - start_time)}s")
                        return True
                    elif status == "failed":
                        error = data.get("error_message", "Unknown error")
                        print(f"\n❌ Job failed: {error}")
                        return False
                else:
                    print(f"   (Status check: {response.status_code})")
                    
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                print(f"   (Polling error: {str(e)[:50]})")
            
            time.sleep(5)
        
        print(f"\n❌ Timeout after {timeout}s")
        return False
    
    def get_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job results including model URLs"""
        try:
            response = requests.get(
                f"{self.api_url}/scans/{job_id}/results",
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting results: {e}")
        
        return None
    
    def download_model(self, url: str, job_id: str, model_type: str = "obj") -> Optional[Path]:
        """Download model from URL"""
        try:
            print(f"\n📥 Downloading {model_type.upper()} model...")
            response = requests.get(url, timeout=60, stream=True)
            
            if response.status_code == 200:
                # Determine filename
                filename = f"{job_id}_{model_type.lower()}.{model_type.lower()}"
                filepath = OUTPUT_DIR / filename
                
                # Download with progress
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                progress = int(downloaded / total_size * 100)
                                print(f"   Progress: {progress}%", end='\r')
                
                print(f"\n✅ Downloaded: {filepath}")
                return filepath
            
        except Exception as e:
            print(f"Download error: {e}")
        
        return None
    
    def process_project(self, image_dir: Path, project_name: str, enable_splat: bool = False):
        """Process a complete project"""
        print(f"\n{'='*70}")
        print(f"🧪 Processing: {project_name}")
        print(f"{'='*70}")
        
        # Upload
        job_id = self.upload_images(image_dir, project_name, enable_splat)
        if not job_id:
            print(f"❌ Failed to create job for {project_name}")
            return
        
        # Poll status
        if not self.poll_job_status(job_id):
            print(f"❌ Job failed or timed out")
            return
        
        # Get results
        results = self.get_results(job_id)
        if not results:
            print(f"❌ Could not fetch results")
            return
        
        print(f"\n📊 Results Summary:")
        print(f"   Job ID: {job_id}")
        print(f"   Status: {results.get('status', 'unknown')}")
        
        # Download models
        models_dir = OUTPUT_DIR / job_id
        models_dir.mkdir(parents=True, exist_ok=True)
        
        if "model_url" in results and results["model_url"]:
            self.download_model(
                results["model_url"], 
                job_id, 
                "ply"
            )
        
        if "splat_url" in results and results["splat_url"]:
            self.download_model(
                results["splat_url"],
                job_id,
                "splat"
            )
        
        self.completed_jobs.append({
            "project": project_name,
            "job_id": job_id,
            "status": results.get('status'),
            "models_dir": str(models_dir)
        })
        
        print(f"✅ Project complete: {project_name}")

def main():
    """Main test execution"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                  🐢 LOCAL 3D MODEL GENERATION TEST 🐢                      ║
║            Generate 3D Models from Turtle and Cube Images                  ║
╚════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize tester
    tester = LocalPipelineTester()
    
    # Check backend
    if not tester.check_backend():
        print("\n❌ Cannot proceed: Backend not running")
        print("   Start the backend with: uvicorn backend.main:app --reload")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("📋 TEST PLAN")
    print("="*70)
    print("1. Generate 3D model from TURTLE images (17 images)")
    print("   - Multiple views: front, back, sides, high angles")
    print("   - Expected: Complete turtle model")
    print("")
    print("2. Generate 3D model from CUBE images (18 images)")
    print("   - Multiple rotations and angles")
    print("   - Expected: Complete cube model")
    print("")
    print(f"Output directory: {OUTPUT_DIR}")
    print("="*70)
    
    # Test 1: Turtle
    turtle_dir = ASSETS_DIR / "turtle_images"
    if turtle_dir.exists():
        tester.process_project(
            turtle_dir,
            "Turtle_3D_Model",
            enable_splat=True
        )
    else:
        print(f"⚠️  Turtle images not found at {turtle_dir}")
    
    # Test 2: Cube
    cube_dir = ASSETS_DIR / "cube_images"
    if cube_dir.exists():
        tester.process_project(
            cube_dir,
            "Cube_3D_Model",
            enable_splat=True
        )
    else:
        print(f"⚠️  Cube images not found at {cube_dir}")
    
    # Summary
    print("\n" + "="*70)
    print("📊 FINAL SUMMARY")
    print("="*70)
    
    if tester.completed_jobs:
        print(f"✅ Completed {len(tester.completed_jobs)} job(s):")
        for job_info in tester.completed_jobs:
            print(f"\n   Project: {job_info['project']}")
            print(f"   Job ID: {job_info['job_id']}")
            print(f"   Status: {job_info['status']}")
            print(f"   Models: {job_info['models_dir']}")
    else:
        print("❌ No jobs completed")
    
    print(f"\n📁 Output directory: {OUTPUT_DIR}")
    print("\n✅ Test suite completed!")

if __name__ == "__main__":
    main()
