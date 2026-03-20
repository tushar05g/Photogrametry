#!/usr/bin/env python3
"""
Test script to run the photogrammetry pipeline on the turtle dataset.
"""

import os
import sys
import glob
import json
import logging
import shutil
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.photogrammetry import PhotogrammetryPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(project_root / "logs" / "turtle_pipeline.log", mode='a')
    ]
)
logger = logging.getLogger(__name__)

def run_test():
    image_dir = project_root / "assets" / "sample_images" / "turtle"
    output_dir = project_root / "output"
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(project_root / "logs", exist_ok=True)

    logger.info(f"🚀 Starting Turtle test pipeline run...")
    logger.info(f"📁 Image directory: {image_dir}")
    
    image_paths = sorted(glob.glob(os.path.join(image_dir, "*.png")))
    
    if not image_paths:
        logger.error("❌ No images found in the directory!")
        return

    logger.info(f"📸 Found {len(image_paths)} images. Initializing pipeline...")

    try:
        pipeline = PhotogrammetryPipeline(use_fallback=False)
        # Set workspace for turtle
        pipeline.workspace = os.path.join(output_dir, "turtle_workspace")
        if os.path.exists(pipeline.workspace):
            shutil.rmtree(pipeline.workspace)
        os.makedirs(pipeline.workspace, exist_ok=True)
        
        result = pipeline.run_pipeline(image_paths, "TurtleTest")
        
        logger.info("\n" + "=" * 60)
        logger.info("FINAL RESULT:")
        logger.info(json.dumps(result, indent=2))
        logger.info("=" * 60)
        
        if result["status"] == "success":
            logger.info(f"✅ Pipeline completed successfully!")
            logger.info(f"📦 Final mesh at: {result['final_mesh']}")
        else:
            logger.error(f"❌ Pipeline failed: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"❌ Unexpected error during pipeline run: {e}", exc_info=True)

if __name__ == "__main__":
    run_test()
