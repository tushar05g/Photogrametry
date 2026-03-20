"""
COLMAP Step - Structure from Motion with robust parameters
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class ColmapStep:
    def execute(self, images_dir, workspace):
        """Run COLMAP with robust parameters for difficult datasets."""
        db_path = os.path.join(workspace, "database.db")
        sparse_dir = os.path.join(workspace, "sparse")
        os.makedirs(sparse_dir, exist_ok=True)
        
        import shutil
        xvfb = ["xvfb-run", "-a"] if shutil.which("xvfb-run") else []
        
        try:
            logger.info("Extracting features (Memory Optimized)...")
            subprocess.run(xvfb + [
                "colmap", "feature_extractor",
                "--database_path", db_path,
                "--image_path", images_dir,
                "--SiftExtraction.use_gpu", "0",
                "--ImageReader.camera_model", "PINHOLE",
                "--ImageReader.single_camera", "1",
                "--SiftExtraction.max_num_features", "4096", # Reduced from 8192
                "--SiftExtraction.max_image_size", "1600"     # Cap image size for memory
            ], check=True, capture_output=True, timeout=600)

            logger.info("Matching features...")
            subprocess.run(xvfb + [
                "colmap", "exhaustive_matcher",
                "--database_path", db_path,
                "--SiftMatching.use_gpu", "0",
                "--SiftMatching.max_distance", "0.7",
                "--SiftMatching.max_ratio", "0.8"
            ], check=True, capture_output=True, timeout=900)

            logger.info("Mapping sparse cloud...")
            result = subprocess.run(xvfb + [
                "colmap", "mapper",
                "--database_path", db_path,
                "--image_path", images_dir,
                "--output_path", sparse_dir,
                "--Mapper.init_min_num_inliers", "3",
                "--Mapper.abs_pose_min_num_inliers", "3",
                "--Mapper.init_min_tri_angle", "1",
                "--Mapper.ba_global_images_ratio", "1.2",
                "--Mapper.min_model_size", "1",
                "--Mapper.init_max_error", "16.0",
                "--Mapper.abs_pose_max_error", "32.0",
                "--Mapper.refine_extra_relative_pose", "True"
            ], check=False, capture_output=True, text=True, timeout=600)
            
            # Check if mapper succeeded
            if result.returncode != 0:
                logger.warning(f"COLMAP mapper failed with code {result.returncode}")
                logger.warning(f"Error output: {result.stderr}")
                logger.warning(f"Standard output: {result.stdout}")
                
                # Try with even more relaxed parameters
                logger.info("Retrying with relaxed parameters...")
                subprocess.run(xvfb + [
                    "colmap", "mapper",
                    "--database_path", db_path,
                    "--image_path", images_dir,
                    "--output_path", sparse_dir,
                    "--Mapper.init_min_num_inliers", "2",
                    "--Mapper.abs_pose_min_num_inliers", "2",
                    "--Mapper.init_min_tri_angle", "0.5",
                    "--Mapper.min_model_size", "0"
                ], check=True, capture_output=True, timeout=600)

            # Check if model was created
            model_0 = os.path.join(sparse_dir, "0")
            if not os.path.exists(model_0):
                logger.error("COLMAP failed to reconstruct any model")
                # List what was created
                if os.path.exists(sparse_dir):
                    logger.info(f"Contents of sparse dir: {os.listdir(sparse_dir)}")
                raise RuntimeError("COLMAP could not reconstruct 3D model from these images. Try taking more photos with better coverage.")

            # Create undistorted output
            undistorted_dir = os.path.join(workspace, "undistorted")
            os.makedirs(undistorted_dir, exist_ok=True)
            
            logger.info("Creating undistorted images...")
            subprocess.run(xvfb + [
                "colmap", "image_undistorter",
                "--image_path", images_dir,
                "--input_path", model_0,
                "--output_path", undistorted_dir,
                "--output_type", "TXT"
            ], check=True, capture_output=True, timeout=300)

            return undistorted_dir
            
        except subprocess.TimeoutExpired:
            logger.error("COLMAP operation timed out")
            raise RuntimeError("COLMAP processing took too long. Try with fewer or smaller images.")
        except Exception as e:
            logger.error(f"COLMAP failed: {e}")
            raise
