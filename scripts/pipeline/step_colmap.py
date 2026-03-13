import os
import subprocess
import logging

logger = logging.getLogger("worker")

class ColmapStep:
    def execute(self, images_dir, workspace):
        db = os.path.join(workspace, "database.db")
        sparse = os.path.join(workspace, "sparse")
        os.makedirs(sparse, exist_ok=True)

        xvfb = ["xvfb-run", "-a"]

        try:
            logger.info("📸 Extracting features...")
            subprocess.run(xvfb + [
                "colmap", "feature_extractor",
                "--database_path", db,
                "--image_path", images_dir,
                "--SiftExtraction.use_gpu", "1"
            ], check=True, capture_output=True)

            logger.info("📸 Matching images...")
            subprocess.run(xvfb + [
                "colmap", "exhaustive_matcher",
                "--database_path", db,
                "--SiftMatching.use_gpu", "1"
            ], check=True, capture_output=True)

            logger.info("📸 Mapping sparse cloud...")
            result = subprocess.run(xvfb + [
                "colmap", "mapper",
                "--database_path", db,
                "--image_path", images_dir,
                "--output_path", sparse,
                "--Mapper.init_min_num_inliers", "15",
                "--Mapper.abs_pose_min_num_inliers", "15",
                "--Mapper.init_min_tri_angle", "0.5"
            ], check=False, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"❌ COLMAP mapper failed. Stderr:\\n{result.stderr[-2000:]}")
                raise RuntimeError(f"COLMAP mapper failed with code {result.returncode}")

            return sparse
        except Exception as e:
            logger.error(f"❌ COLMAP failed: {e}")
            raise RuntimeError(f"COLMAP failed: {e}")
