import os
import sys
import subprocess
import glob
import logging
import time
import shutil

logger = logging.getLogger(__name__)

class GSREngine:
    def __init__(self, workspace, cancel_check_func=None):
        self.workspace = workspace
        self.cancel_check_func = cancel_check_func
        self.sparse_dir = os.path.join(workspace, "sparse")
        self.images_dir = os.path.join(workspace, "images")
        self.output_dir = os.path.join(workspace, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def check_cancel(self):
        if self.cancel_check_func and self.cancel_check_func():
            logger.info("🛑 Cancellation detected. Stopping engine...")
            raise RuntimeError("Job cancelled by user.")

    def run_sfm(self):
        """COLMAP Structure-from-Motion stage."""
        db_path = os.path.join(self.workspace, "database.db")
        os.makedirs(self.sparse_dir, exist_ok=True)
        xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]

        self.check_cancel()
        logger.info("📸 Running COLMAP: Feature Extraction...")
        # ✅ FIXED: Force OPENCV camera model for better GS compatibility
        subprocess.run(xvfb + [
            "colmap", "feature_extractor",
            "--database_path", db_path,
            "--image_path", self.images_dir,
            "--ImageReader.camera_model", "OPENCV",
            "--SiftExtraction.use_gpu", "1"
        ], check=True)

        self.check_cancel()
        logger.info("📸 Running COLMAP: Exhaustive Matcher...")
        subprocess.run(xvfb + [
            "colmap", "exhaustive_matcher",
            "--database_path", db_path,
            "--SiftMatching.use_gpu", "1",
            "--SiftMatching.guided_matching", "1"
        ], check=True)

        self.check_cancel()
        logger.info("📸 Running COLMAP: Mapper (Robust Mode)...")
        subprocess.run(xvfb + [
            "colmap", "mapper",
            "--database_path", db_path,
            "--image_path", self.images_dir,
            "--output_path", self.sparse_dir,
            "--Mapper.init_min_num_inliers", "12",
            "--Mapper.abs_pose_min_num_inliers", "10",
            "--Mapper.min_model_size", "3",
            "--Mapper.ba_global_images_ratio", "1.1",
            "--Mapper.num_threads", "-1"
        ], check=True)

        # ✅ FIXED: Validate sparse reconstruction count
        points_file = os.path.join(self.sparse_dir, "0", "points3D.bin")
        if not os.path.exists(points_file):
             # Try .txt if mapper produced text output
             points_file = os.path.join(self.sparse_dir, "0", "points3D.txt")
        
        if not os.path.exists(points_file):
            raise RuntimeError("COLMAP failed to produce sparse points.")
        
        # Simple size check: if bin is < 1KB, it's likely empty
        if os.path.getsize(points_file) < 500:
            raise RuntimeError("Sparse reconstruction too thin (not enough points).")

        return True

    def train_3dgs_nerfstudio(self):
        """Primary: Nerfstudio splatfacto."""
        logger.info("✨ Training with Nerfstudio (splatfacto)...")
        xvfb = ["xvfb-run", "-a", "-s", "-screen 0 1024x768x24"]
        
        try:
            # Training
            subprocess.run(xvfb + [
                "ns-train", "splatfacto", "colmap",
                "--data", self.workspace,
                "--max-num-iterations", "7000",
                "--viewer.quit-on-train-completion", "True",
                "--output-dir", self.output_dir
            ], check=True, timeout=3600)

            # Export
            config = glob.glob(os.path.join(self.output_dir, "**/config.yml"), recursive=True)[0]
            subprocess.run(xvfb + [
                "ns-export", "gaussian-splat",
                "--load-config", config,
                "--output-dir", self.output_dir
            ], check=True)
            
            output_ply = os.path.join(self.output_dir, "splat.ply")
            if os.path.exists(output_ply):
                return output_ply
        except Exception as e:
            logger.warning(f"⚠️ Nerfstudio failed: {e}. Falling back...")
        return None

    def train_3dgs_original(self):
        """Fallback 1: Original Inria 3DGS Repo."""
        logger.info("✨ Falling back to original Gaussian Splatting repo...")
        # Check if already cloned
        repo_dir = "/kaggle/working/gaussian-splatting"
        if not os.path.exists(repo_dir):
            subprocess.run(["git", "clone", "https://github.com/graphdeco-inria/gaussian-splatting", "--recursive", repo_dir], check=True)
            # Minimal install via pip for its submodules
            subprocess.run([sys.executable, "-m", "pip", "install", os.path.join(repo_dir, "submodules/diff-gaussian-rasterization")], check=True)
            subprocess.run([sys.executable, "-m", "pip", "install", os.path.join(repo_dir, "submodules/simple-knn")], check=True)

        try:
            train_script = os.path.join(repo_dir, "train.py")
            subprocess.run([
                sys.executable, train_script,
                "-s", self.workspace,
                "-m", os.path.join(self.output_dir, "original_gs"),
                "--iterations", "7000"
            ], check=True, timeout=3600)
            
            # Original repo puts output in output_dir/point_cloud/iteration_7000/point_cloud.ply
            ply_path = os.path.join(self.output_dir, "original_gs", "point_cloud", "iteration_7000", "point_cloud.ply")
            if os.path.exists(ply_path):
                return ply_path
        except Exception as e:
            logger.warning(f"⚠️ Original GS repo failed: {e}")
        return None

    def dense_reconstruction_fallback(self):
        """Fallback 2 & 3: Dense Reconstruction or Sparse Export."""
        logger.info("📐 Applying Fallback: COLMAP Model Converter (Sparse PLY)")
        ply_path = os.path.join(self.output_dir, "fallback_sparse.ply")
        try:
            subprocess.run([
                "colmap", "model_converter",
                "--input_path", os.path.join(self.sparse_dir, "0"),
                "--output_path", ply_path,
                "--output_type", "PLY"
            ], check=True)
            return ply_path
        except Exception as e:
            logger.error(f"❌ Fallback sparse export failed: {e}")
        return None

    def run(self):
        """Full pipeline execution with internal fallbacks."""
        self.run_sfm()
        
        # Trigger Fallback Chain
        self.check_cancel()
        result = self.train_3dgs_nerfstudio()
        self.check_cancel()
        if not result:
            result = self.train_3dgs_original()
        self.check_cancel()
        if not result:
            result = self.dense_reconstruction_fallback()
            
        if not result or not os.path.exists(result):
            raise RuntimeError("CRITICAL: Pipeline failed to produce ANY .ply artifact.")
            
        return result
