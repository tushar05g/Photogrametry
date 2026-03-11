import os
import glob
import subprocess
import logging

logger = logging.getLogger("worker")

class SplattingStep:
    def execute(self, workspace):
        output_dir = os.path.join(workspace, "splat")
        
        try:
            logger.info("✨ Starting Nerfstudio Splatfacto training...")
            subprocess.run([
                "ns-train", "splatfacto",
                "colmap",
                "--data", workspace,
                "--max-num-iterations", "3000",
                "--viewer.quit-on-train-completion", "True",
                "--output-dir", output_dir
            ], check=True, capture_output=True)

            # Find the trained config
            config_files = glob.glob(os.path.join(output_dir, "/**/config.yml"), recursive=True)
            if not config_files:
                raise RuntimeError("Training completed but config.yml not found.")
            
            config = config_files[0]

            logger.info("✨ Exporting Gaussian Splats to PLY...")
            subprocess.run([
                "ns-export", "gaussian-splat",
                "--load-config", config,
                "--output-dir", output_dir
            ], check=True, capture_output=True)

            return os.path.join(output_dir, "splat.ply")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Splatting failed: {e.stderr.decode()}")
            # FALLBACK: Return None so controller can decide to use sparse points
            return None
