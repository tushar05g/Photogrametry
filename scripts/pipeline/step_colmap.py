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
            subprocess.run(xvfb + [
                "colmap", "mapper",
                "--database_path", db,
                "--image_path", images_dir,
                "--output_path", sparse
            ], check=True, capture_output=True)

            return sparse
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ COLMAP failed: {e.stderr.decode()}")
            raise RuntimeError(f"COLMAP failed: {e}")
