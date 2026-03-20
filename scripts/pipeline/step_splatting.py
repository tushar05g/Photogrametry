"""
Gaussian Splatting Step - Handles both Nerfstudio and original repo
"""

import os
import glob
import subprocess
import logging
import sys

logger = logging.getLogger(__name__)

class SplattingStep:
    def execute(self, workspace, data_dir=None):
        """Try Nerfstudio first, fallback to original repo."""
        if data_dir is None:
            data_dir = workspace
            
        # Check Python version
        if sys.version_info >= (3, 12):
            logger.warning("Python 3.12+ detected, using original Gaussian Splatting")
            return self._original_gaussian_splatting(data_dir)
        
        try:
            logger.info("Starting Nerfstudio training...")
            output_dir = os.path.join(workspace, "splat")
            
            subprocess.run([
                "ns-train", "splatfacto",
                "colmap",
                "--data", data_dir,
                "--max-num-iterations", "3000",
                "--viewer.quit-on-train-completion", "True",
                "--output-dir", output_dir
            ], check=True)

            # Find config and export
            config_files = glob.glob(os.path.join(output_dir, "**/config.yml"), recursive=True)
            if not config_files:
                raise RuntimeError("Training completed but no config found")
            
            subprocess.run([
                "ns-export", "gaussian-splat",
                "--load-config", config_files[0],
                "--output-dir", output_dir
            ], check=True)

            return os.path.join(output_dir, "splat.ply")
            
        except Exception as e:
            logger.warning(f"Nerfstudio failed: {e}, trying original repo")
            return self._original_gaussian_splatting(workspace)
    
    def _original_gaussian_splatting(self, data_dir):
        """Use original Gaussian Splatting repository."""
        try:
            gs_dir = "/kaggle/working/gaussian-splatting"
            if not os.path.exists(gs_dir):
                subprocess.run([
                    "git", "clone", 
                    "https://github.com/graphdeco-inria/gaussian-splatting.git",
                    gs_dir
                ], check=True)
            
            # Install dependencies
            subprocess.run([
                "pip", "install", "-q",
                "torch", "torchvision", "matplotlib", "numpy", "tqdm"
            ])
            
            # Build
            subprocess.run([
                "python", "setup.py", "install_ext", "--no_cuda_ext"
            ], cwd=gs_dir, check=True)
            
            # Train
            output_dir = os.path.join(os.path.dirname(data_dir), "splat_orig")
            subprocess.run([
                "python", "train.py",
                "-s", data_dir,
                "-m", output_dir,
                "--iterations", "7000"
            ], cwd=gs_dir, check=True)
            
            return os.path.join(output_dir, "point_cloud", "iteration_7000", "point_cloud.ply")
            
        except Exception as e:
            logger.error(f"Original Gaussian Splatting failed: {e}")
            return None
