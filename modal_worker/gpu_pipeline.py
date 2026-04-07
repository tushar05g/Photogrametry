import os
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Dict, Optional
import cv2
import numpy as np
from storage.provider import StorageProvider

logger = logging.getLogger(__name__)

class GPUPipeline:
    def __init__(self, workspace: Path, storage: StorageProvider, job_id: str):
        self.workspace = workspace
        self.storage = storage
        self.job_id = job_id
        
        # Paths inside the temporary workspace
        self.images_dir = self.workspace / "images"
        self.sparse_dir = self.workspace / "sparse"
        self.dense_dir = self.workspace / "dense"
        self.db_path = self.workspace / "database.db"
        
        # Constants
        self.MESH_OBJ = "mesh.obj"
        self.MESH_RAW_PLY = "mesh_raw.ply"
        self.DENSE_PLY = "dense.ply"
        
        # Ensure directories exist
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.sparse_dir.mkdir(parents=True, exist_ok=True)
        self.dense_dir.mkdir(parents=True, exist_ok=True)

    def run_command(self, cmd: List[str], stage_tag: str):
        logger.info(f"🚀 Running {stage_tag}: {' '.join(cmd)}")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Log stdout snippets for transparency
        if result.stdout:
            lines = result.stdout.splitlines()
            if len(lines) > 20:
                logger.info(f"[{stage_tag} STDOUT (Head)]\n" + "\n".join(lines[:10]))
                logger.info(f"[{stage_tag} STDOUT (Tail)]\n" + "\n".join(lines[-10:]))
            else:
                logger.info(f"[{stage_tag} STDOUT]\n" + result.stdout)

        if result.returncode != 0:
            logger.error(f"❌ Error in {stage_tag}: {result.stderr}")
            raise RuntimeError(f"Command failed during {stage_tag}: {result.stderr}")
        return result.stdout

    def pull_input(self, stage: str):
        """
        Pull necessary files from storage for a specific stage.
        """
        if stage == "SFM":
            # Pull from input/preprocessed
            remote_prefix = f"jobs/{self.job_id}/input/preprocessed/"
            files = self.storage.list_files(remote_prefix)
            for f in files:
                self.storage.download_file(f, self.images_dir / Path(f).name)
        
        elif stage in ["MVS", "MESH"]:
            # Pull preprocessed images and sparse model from output/sparse
            remote_img_prefix = f"jobs/{self.job_id}/input/preprocessed/"
            files = self.storage.list_files(remote_img_prefix)
            for f in files:
                self.storage.download_file(f, self.images_dir / Path(f).name)
            
            # Sparse results
            remote_sparse_prefix = f"jobs/{self.job_id}/output/sparse/"
            files = self.storage.list_files(remote_sparse_prefix)
            for f in files:
                rel_path = Path(f).relative_to(remote_sparse_prefix)
                dest = self.sparse_dir / rel_path
                self.storage.download_file(f, dest)

            # 🏁 v8.2.1: Pull dense point cloud if we are meshing
            if stage == "MESH":
                remote_dense_prefix = f"jobs/{self.job_id}/output/dense/"
                files = self.storage.list_files(remote_dense_prefix)
                for f in files:
                    if f.endswith(self.DENSE_PLY):
                        dest = self.dense_dir / self.DENSE_PLY
                        self.storage.download_file(f, dest)
                        logger.info(f"✅ Pulled dense point cloud: {f}")

    def push_output(self, stage: str):
        """
        Push results of a specific stage back to storage.
        """
        if stage == "SFM":
            # Push sparse model results to output/sparse/
            for p in self.sparse_dir.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(self.sparse_dir)
                    dest_key = f"jobs/{self.job_id}/output/sparse/{rel}"
                    self.storage.upload_file(dest_key, p)
                    logger.info(f"📤 Uploaded sparse file: {rel}")
        
        elif stage == "MVS":
            # Push dense results to output/dense/
            dense_ply = self.dense_dir / self.DENSE_PLY
            if dense_ply.exists():
                dest_key = f"jobs/{self.job_id}/output/dense/{self.DENSE_PLY}"
                self.storage.upload_file(dest_key, dense_ply)
                logger.info(f"📤 Uploaded dense point cloud: {self.DENSE_PLY}")
            else:
                logger.error(f"❌ Failed to find {self.DENSE_PLY} for upload after MVS!")
        
        elif stage == "MESH":
            # Push mesh results to output/dense/
            mesh_obj = self.dense_dir / self.MESH_OBJ
            if mesh_obj.exists():
                dest_key = f"jobs/{self.job_id}/output/dense/{self.MESH_OBJ}"
                self.storage.upload_file(dest_key, mesh_obj)
                logger.info(f"📤 Uploaded final mesh: {self.MESH_OBJ}")
            else:
                logger.error(f"❌ Failed to find {self.MESH_OBJ} for upload after MESH!")

    def run_sfm(self, robust: bool = True):
        try:
            self.run_command([
                "colmap", "automatic_reconstructor",
                "--image_path", str(self.images_dir),
                "--workspace_path", str(self.workspace),
                "--data_type", "individual",
                "--quality", "high",
                "--use_gpu", "1"
            ], "SFM_AUTO")
            
            # Check if auto model exists; if not, retry manual
            if not self._has_valid_sparse_model():
                raise RuntimeError("Auto reconstruction produced no sparse model")
                
        except Exception as e:
            if not robust: raise e
            logger.warning(f"⚠️ Automatic SFM failed or produced no matches: {e}")
            self._run_sfm_manual_relaxed()
            
            # Final check
            if not self._has_valid_sparse_model():
                raise RuntimeError("Poor image quality/overlap: All reconstruction attempts failed to find enough 3D tie points.")

    def _has_valid_sparse_model(self) -> bool:
        if not self.sparse_dir.exists(): return False
        # Check for non-empty subdirs (0, 1, etc)
        models = [d for d in self.sparse_dir.iterdir() if d.is_dir()]
        return len(models) > 0

    def _run_sfm_manual_relaxed(self):
        """Refactored SFM pipeline with lower cognitive complexity."""
        logger.info("🔧 Starting Manual SFM with High Sensitivity...")
        self._sfm_extract_features()
        self._sfm_match_features()
        self._sfm_mapper()

    def _sfm_extract_features(self):
        """Helper: Feature extraction."""
        self.run_command([
            "colmap", "feature_extractor", 
            "--database_path", str(self.db_path), 
            "--image_path", str(self.images_dir),
            "--ImageReader.camera_model", "RADIAL",
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.max_num_features", "16384"  # Increased from 8k
        ], "SFM_FE_RELAXED")

    def _sfm_match_features(self):
        """Helper: Feature matching."""
        self.run_command([
            "colmap", "exhaustive_matcher", 
            "--database_path", str(self.db_path)
        ], "SFM_MATCH_RELAXED")

    def _sfm_mapper(self):
        """Helper: Mapper."""
        self.run_command([
            "colmap", "mapper",
            "--database_path", str(self.db_path),
            "--image_path", str(self.images_dir),
            "--output_path", str(self.sparse_dir),
            "--Mapper.init_min_num_inliers", "10",      # More robust initialization
            "--Mapper.abs_pose_min_num_inliers", "10",   # More robust registration
            "--Mapper.init_min_tri_angle", "8.0",        # More reliable triangulation
            "--Mapper.min_model_size", "3",
            "--Mapper.tri_min_angle", "2.0"
        ], "SFM_MAP_RELAXED")

    def run_mvs(self):
        # The automatic_reconstructor might put results in sparse/0
        sparse_model = self.sparse_dir / "0"
        if not sparse_model.exists():
            models = sorted([d for d in self.sparse_dir.iterdir() if d.is_dir()])
            if not models: raise RuntimeError("No sparse model found for MVS")
            sparse_model = models[0]

        self.run_command([
            "colmap", "image_undistorter", 
            "--image_path", str(self.images_dir), 
            "--input_path", str(sparse_model), 
            "--output_path", str(self.dense_dir)
        ], "MVS_UNDISTORT")
        
        self.run_command([
            "colmap", "patch_match_stereo", 
            "--workspace_path", str(self.dense_dir)
        ], "MVS_STEREO")
        
        self.run_command([
            "colmap", "stereo_fusion", 
            "--workspace_path", str(self.dense_dir), 
            "--output_path", str(self.dense_dir / "dense.ply")
        ], "MVS_FUSION")

    def _find_pml_filter(self, ms, keyword: str) -> str:
        """Helper to find the best available PyMeshLab filter name."""
        try:
            filters = ms.filter_list()
            # Priority 1: Exact match (case insensitive)
            for f in filters:
                if keyword.lower() == f.lower():
                    return f
            
            # Priority 2: Fuzzy match with EXCLUSION of sampling
            # This is critical to avoid 'generate_sampling_poisson_disk'
            matches = [f for f in filters if keyword.lower() in f.lower()]
            if 'poisson' in keyword.lower() or 'reconstruction' in keyword.lower():
                matches = [m for m in matches if 'sampling' not in m.lower() and 'disk' not in m.lower()]
            
            if matches:
                # Return the shortest match (usually the most specific/standard)
                return min(matches, key=len)
            
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error in _find_pml_filter: {e}")
            return None

    def run_mesh(self):
        dense_ply = self.dense_dir / self.DENSE_PLY
        if not dense_ply.exists(): 
            raise RuntimeError(f"No {self.DENSE_PLY} found for meshing")
        
        final_mesh_obj = self.dense_dir / self.MESH_OBJ
        
        # Using PyMeshLab for robust meshing and colorization
        try:
            import pymeshlab
            logger.info("📐 Generating mesh using PyMeshLab (Screened Poisson)...")
            ms = pymeshlab.MeshSet()
            
            # Load the dense point cloud
            ms.load_new_mesh(str(dense_ply))
            m = ms.current_mesh()
            logger.info(f"📊 Input point cloud: {m.vertex_number()} vertices")
            
            # --- Step 0: Ensure normals exist (REQUIRED for Poisson) ---
            has_norms = False
            try:
                # Plural or singular check
                has_norms = getattr(m, 'has_vertex_normals', lambda: False)() or \
                            getattr(m, 'has_vertex_normal', lambda: False)()
            except:
                try: m.vertex_normal_matrix(); has_norms = True
                except: pass
            
            if not has_norms:
                logger.info("📐 Point cloud missing normals, computing them (k=30 for stability)...")
                nf = self._find_pml_filter(ms, "compute_normal_for_point_sets") or \
                     self._find_pml_filter(ms, "compute_normal_for_vertex") or \
                     self._find_pml_filter(ms, "normal")
                if nf:
                    try: ms.apply_filter(nf, k=30)
                    except: 
                        try: ms.apply_filter(nf)
                        except: pass
            
            # --- Step 1: Screened Poisson Reconstruction ---
            # Search specifically for reconstruction names
            pf = self._find_pml_filter(ms, "screened_poisson") or \
                 self._find_pml_filter(ms, "surface_reconstruction") or \
                 self._find_pml_filter(ms, "poisson")
            
            if pf:
                logger.info(f"📐 Applying Reconstruction using filter: {pf}")
                try:
                    if "poisson" in pf.lower():
                        ms.apply_filter(pf, depth=8, samplespernode=1, pointweight=4)
                    else:
                        ms.apply_filter(pf)
                except Exception as e:
                    logger.warning(f"⚠️ Primary reconstruction failed: {e}. Trying Ball Pivoting fallback...")
            
            # --- Step 1.5: Final Fallback to Ball Pivoting if reconstruction failed to add/populate a mesh ---
            reconstruction_success = False
            if ms.number_of_meshes() > 1:
                ms.set_current_mesh(1)
                if ms.current_mesh().vertex_number() > 0:
                    reconstruction_success = True
            
            if not reconstruction_success:
                logger.warning("🔄 Reconstruction failed to produce geometry. Attempting Ball Pivoting...")
                bpf = self._find_pml_filter(ms, "ball_pivoting") or \
                      self._find_pml_filter(ms, "reconstruction")
                if bpf:
                    # Reset to base point cloud (mesh 0) before trying another reconstruction
                    ms.set_current_mesh(0)
                    try: 
                        ms.apply_filter(bpf)
                        if ms.number_of_meshes() > 1:
                            ms.set_current_mesh(ms.number_of_meshes() - 1)
                            if ms.current_mesh().vertex_number() > 0:
                                reconstruction_success = True
                    except: pass
            
            # Verify we have geometry now
            if not reconstruction_success or ms.number_of_meshes() < 2:
                raise RuntimeError("All reconstruction attempts failed to produce a valid mesh from the point cloud.")
                
            m_reconstructed = ms.current_mesh()
            logger.info(f"📐 Geometry verified: {m_reconstructed.vertex_number()} vertices")
            
            # --- Step 2: Color Transfer ---
            # Link color from Mesh 0 (Dense PLY) to the LAST added mesh (Reconstructed)
            target_idx = ms.number_of_meshes() - 1
            ms.set_current_mesh(0)
            has_colors = False
            try:
                curr_m = ms.current_mesh()
                has_colors = getattr(curr_m, 'has_vertex_colors', lambda: False)() or \
                             getattr(curr_m, 'has_vertex_color', lambda: False)()
            except: pass
            
            if has_colors:
                logger.info(f"🎨 Transferring vertex colors to mesh index {target_idx}...")
                tf = self._find_pml_filter(ms, "transfer_attributes_to_mesh") or \
                     self._find_pml_filter(ms, "transfer")
                if tf:
                    try: 
                        # Use the actual indices in the filter call
                        ms.apply_filter(tf, sourcemesh=0, targetmesh=target_idx, colortransfer=True)
                    except Exception as te:
                        logger.warning(f"⚠️ Color transfer failed: {te}")
            
            # Back to the generated mesh for smoothing and save
            ms.set_current_mesh(target_idx)
            
            # --- Step 3: Final Smoothing and Save ---
            sf = self._find_pml_filter(ms, "laplacian_smooth") or \
                 self._find_pml_filter(ms, "smooth")
            if sf: 
                try: ms.apply_filter(sf, stepsmoothnum=3)
                except: pass
            
            # Final Save
            ms.save_current_mesh(str(final_mesh_obj), save_vertex_color=True)
            logger.info(f"✅ Mesh generation complete: {final_mesh_obj.name}")
            
        except Exception as e:
            logger.error(f"❌ PyMeshLab meshing failed: {e}")
            # Final fallback: try raw colmap mesh if it exists
            logger.info("Attempting COLMAP poisson_mesher fallback...")
            mesh_raw_path = self.dense_dir / self.MESH_RAW_PLY
            try:
                import shutil
                self.run_command([
                    "colmap", "poisson_mesher", 
                    "--input_path", str(dense_ply), 
                    "--output_path", str(mesh_raw_path),
                    "--PoissonMeshing.depth", "8"
                ], "MVS_MESH_POISSON_FALLBACK")
                if mesh_raw_path.exists():
                    shutil.copy(mesh_raw_path, final_mesh_obj)
                else:
                    raise RuntimeError("COLMAP poisson_mesher did not produce output")
            except Exception as fe:
                logger.error(f"❌ Fallback failed: {fe}")
                raise RuntimeError(f"Failed to generate mesh: {e}")

    def run_splat(self):
        # Placeholder for Splatting logic
        splat_file = self.workspace / "model.splat"
        splat_file.touch()
        self.storage.upload_file(f"jobs/{self.job_id}/output/model.splat", splat_file)
        return splat_file
