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
        
        # 🏁 v11.0.1: Headless environment support
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["XDG_RUNTIME_DIR"] = "/tmp/runtime-root"
        Path("/tmp/runtime-root").mkdir(parents=True, exist_ok=True)
        try:
            os.chmod("/tmp/runtime-root", 0o700)
        except Exception as e:
            logger.warning(f"Could not set 0700 permissions on /tmp/runtime-root: {e}")
        
        # Paths inside the temporary workspace
        self.images_dir = self.workspace / "images"
        self.sparse_dir = self.workspace / "sparse"
        self.dense_dir = self.workspace / "dense"
        self.db_path = self.workspace / "database.db"
        
        # Constants
        self.MESH_OBJ = "mesh.obj"
        self.MESH_RAW_PLY = "mesh_raw.ply"
        self.DENSE_PLY = "dense.ply"
        self.SPLAT_FILE = "model.splat"
        self.SPLAT_PREVIEW_PLY = "model_splat_preview.ply"
        self.SPLAT_PREVIEW_GLB = "model_splat_preview.glb"
        self.splat_metrics: Dict[str, object] = {}
        
        # Ensure directories exist
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.sparse_dir.mkdir(parents=True, exist_ok=True)
        self.dense_dir.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        """
        🏁 v10.4.1: Environment-Aware Cleanup Logic
        Safely removes temporary artifacts from locally or persistent storage.
        """
        logger.info(f"🧹 Performing cleanup for job {self.job_id}")
        
        # Determine base directory
        # If /mnt/storage exists, we are likely on Modal with a Volume
        storage_base = Path("/mnt/storage/jobs") / self.job_id if Path("/mnt/storage").exists() else self.workspace
        
        # Paths to remove
        to_delete = [
            storage_base / "temp",
            storage_base / "input" / "preprocessed",
            self.images_dir,
            self.db_path
        ]
        
        results = {}
        for p in to_delete:
            if p.exists():
                try:
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
                    logger.info(f"✅ Deleted: {p}")
                    results[str(p)] = "deleted"
                except Exception as e:
                    logger.warning(f"⚠️ Failed to delete {p}: {e}")
                    results[str(p)] = f"error: {e}"
            else:
                results[str(p)] = "not_found"
        
        return results

    def run_command(self, cmd: List[str], stage_tag: str):
        logger.info(f"🚀 Running {stage_tag}: {' '.join(cmd)}")
        env = os.environ.copy()
        env["QT_QPA_PLATFORM"] = "offscreen"
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Log STDOUT
        if result.stdout:
            lines = result.stdout.splitlines()
            # 🏁 v10.0.0: Log more for debugging
            if len(lines) > 100:
                logger.info(f"[{stage_tag} STDOUT (Head)]\n" + "\n".join(lines[:50]))
                logger.info(f"[{stage_tag} STDOUT (Tail)]\n" + "\n".join(lines[-50:]))
            else:
                logger.info(f"[{stage_tag} STDOUT]\n" + result.stdout)

        if result.returncode != 0:
            logger.error(f"❌ Error in {stage_tag}: {result.stderr}")
            # Log the tail of stdout on error too, it might have useful context
            if result.stdout:
                tail = "\n".join(result.stdout.splitlines()[-20:])
                logger.error(f"[{stage_tag} STDOUT TAIL ON ERROR]\n{tail}")
            raise RuntimeError(f"Command failed during {stage_tag}: {result.stderr}")
        return result.stdout

    def pull_input(self, stage: str):
        """
        Pull necessary files from storage for a specific stage.
        """
        def _download_if_missing(remote_path: str, dest: Path):
            if dest.exists() and dest.stat().st_size > 0:
                logger.info(f"⏭️ Reusing cached input file: {dest.name}")
                return
            self.storage.download_file(remote_path, dest)

        if stage == "SFM":
            # Pull from input/preprocessed
            remote_prefix = f"jobs/{self.job_id}/input/preprocessed/"
            logger.info(f"📥 SFM: Listing files in {remote_prefix}")
            files = self.storage.list_files(remote_prefix)
            logger.info(f"📥 SFM: Found {len(files)} files to download")
            for f in files:
                dest = self.images_dir / Path(f).name
                _download_if_missing(f, dest)
            
            logger.info(f"📥 SFM: Download complete. Workspace images count: {len(list(self.images_dir.glob('*')))}")
        
        elif stage in ["MVS", "MESH", "SPLAT"]:
            # Pull preprocessed images and sparse model from output/sparse
            remote_img_prefix = f"jobs/{self.job_id}/input/preprocessed/"
            files = self.storage.list_files(remote_img_prefix)
            for f in files:
                _download_if_missing(f, self.images_dir / Path(f).name)
            
            # Sparse results are required by MVS/MESH and used as SPLAT fallback source.
            if stage in ["MVS", "MESH", "SPLAT"]:
                remote_sparse_prefix = f"jobs/{self.job_id}/output/sparse/"
                
                # Retry listing with backoff — defends against Cloudinary indexing
                # lag and Modal volume commit propagation delay.
                import time
                files = []
                for attempt in range(5):
                    files = self.storage.list_files(remote_sparse_prefix)
                    if files:
                        break
                    wait = 5 * (attempt + 1)  # 5, 10, 15, 20, 25 seconds
                    logger.warning(
                        f"⏳ Sparse listing empty (attempt {attempt+1}/5), "
                        f"retrying in {wait}s for {self.job_id}"
                    )
                    time.sleep(wait)
                
                logger.info(f"📥 Sparse: Found {len(files)} files in {remote_sparse_prefix}")
                
                # 🏁 v10.1.1: Guaranteed relative path reconstruction
                # Ensure prefix ends with a slash for clean slicing
                base_prefix = str(remote_sparse_prefix).rstrip("/") + "/"
                
                for f in files:
                    if f.startswith(base_prefix):
                        rel_path = f[len(base_prefix):]
                        logger.info(f"📥 Sparse: Normalized relative path: {rel_path}")
                    else:
                        rel_path = Path(f).name
                        logger.warning(f"⚠️ Falling back to filename for {f} (Prefix mismatch: {base_prefix})")
                        
                    dest = self.sparse_dir / rel_path
                    logger.info(f"📥 Sparse: Downloading {f} to {dest}")
                    _download_if_missing(f, dest)

            # Pull dense artifacts needed by MESH/SPLAT
            if stage in ["MESH", "SPLAT"]:
                remote_dense_prefix = f"jobs/{self.job_id}/output/dense/"
                try:
                    files = self.storage.list_files(remote_dense_prefix)
                except Exception as e:
                    if stage == "SPLAT":
                        logger.warning(
                            f"SPLAT proceeding without dense artifacts for {self.job_id}: {e}"
                        )
                        files = []
                    else:
                        raise RuntimeError(
                            f"Failed to list dense artifacts for SPLAT at {remote_dense_prefix}: {e}"
                        ) from e
                for f in files:
                    filename = Path(f).name
                    if filename == self.DENSE_PLY:
                        dest = self.dense_dir / filename
                        _download_if_missing(f, dest)
                        logger.info(f"✅ Pulled dense point cloud: {f}")
                    elif filename == self.MESH_OBJ:
                        dest = self.dense_dir / filename
                        _download_if_missing(f, dest)
                        logger.info(f"✅ Pulled mesh artifact: {f}")

    def push_output(self, stage: str) -> Dict[str, object]:
        """
        Push results of a specific stage back to storage.
        Returns a dictionary of result names and their URLs.
        """
        results = {}
        if stage == "SFM":
            # Push sparse model results to output/sparse/
            sparse_files = list(self.sparse_dir.rglob("*"))
            logger.info(f"📤 SFM: Found {len(sparse_files)} items in sparse_dir")
            for p in sparse_files:
                if p.is_file():
                    rel = p.relative_to(self.sparse_dir)
                    
                    # Skip .bin files and convert to PLY instead
                    if str(rel).endswith(".bin"):
                        if "points3D" in str(rel):
                            logger.info(f"⚙️  Converting .bin to .ply: {rel}")
                            # Convert COLMAP .bin to PLY for cloud storage compatibility
                            sparse_model = self.sparse_dir / p.parent.name
                            ply_output = p.parent / "points3D.ply"
                            try:
                                self.run_command([
                                    "colmap", "model_converter",
                                    "--input_path", str(sparse_model),
                                    "--output_path", str(ply_output),
                                    "--output_type", "PLY"
                                ], "SFM_BIN_TO_PLY")
                                if ply_output.exists():
                                    rel = ply_output.relative_to(self.sparse_dir)
                                    p = ply_output
                                    logger.info(f"✅ Converted to: {rel}")
                            except Exception as e:
                                logger.warning(f"Failed to convert .bin to .ply: {e}")
                                continue
                        else:
                            logger.info(f"⏭️  Skipping non-points3D .bin file: {rel}")
                            continue
                    
                    dest_key = f"jobs/{self.job_id}/output/sparse/{rel}"
                    logger.info(f"📤 SFM: Uploading {rel} to {dest_key}")
                    try:
                        url = self.storage.upload_file(dest_key, p)
                        if str(rel) in ["points3D.bin", "points3D.ply"]:
                            results["sparse_pcd"] = url
                        logger.info(f"📤 Uploaded sparse file: {rel}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to upload {rel}: {e}. Continuing with other files...")
            # Export a stable sparse points metric for downstream quality diagnosis.
            sparse_model = self.sparse_dir / "0"
            if not sparse_model.exists():
                models = sorted([d for d in self.sparse_dir.iterdir() if d.is_dir()]) if self.sparse_dir.exists() else []
                if models:
                    sparse_model = models[0]
            if sparse_model.exists():
                sparse_ply = self.workspace / "sparse_points_metrics.ply"
                try:
                    self.run_command([
                        "colmap", "model_converter",
                        "--input_path", str(sparse_model),
                        "--output_path", str(sparse_ply),
                        "--output_type", "PLY"
                    ], "SFM_POINTS_METRICS")
                    results["sparse_points"] = self._ply_point_count(sparse_ply)
                except Exception as e:
                    logger.warning(f"Could not compute sparse points metric: {e}")
        
        elif stage == "MVS":
            # Push dense results to output/dense/
            dense_ply = self.dense_dir / self.DENSE_PLY
            if dense_ply.exists():
                if dense_ply.stat().st_size <= 0:
                    raise RuntimeError(f"MVS produced empty dense point cloud: {dense_ply}")
                dest_key = f"jobs/{self.job_id}/output/dense/{self.DENSE_PLY}"
                results["dense_pcd"] = self.storage.upload_file(dest_key, dense_ply)
                results["point_count"] = self._ply_point_count(dense_ply)
                logger.info(f"📤 Uploaded dense point cloud: {self.DENSE_PLY}. Points: {results['point_count']}")
            else:
                logger.error(f"❌ Failed to find {self.DENSE_PLY} for upload after MVS!")
        
        elif stage == "MESH":
            # Push mesh results to output/dense/
            mesh_obj = self.dense_dir / self.MESH_OBJ
            if mesh_obj.exists():
                dest_key = f"jobs/{self.job_id}/output/dense/{self.MESH_OBJ}"
                results["mesh"] = self.storage.upload_file(dest_key, mesh_obj)
                
                # Capture point count from mesh for final reporting
                import trimesh
                try:
                    m = trimesh.load(str(mesh_obj), process=False)
                    results["point_count"] = len(m.vertices) if hasattr(m, 'vertices') else 0
                except Exception:
                    results["point_count"] = 0

                # Push GLB if exists
                mesh_glb = self.dense_dir / "mesh.glb"
                if mesh_glb.exists():
                    glb_key = f"jobs/{self.job_id}/output/dense/mesh.glb"
                    results["mesh_glb"] = self.storage.upload_file(glb_key, mesh_glb)
                
                logger.info(f"📤 Uploaded final mesh formats for {self.job_id}. Points: {results['point_count']}")
            else:
                logger.error(f"❌ Failed to find {self.MESH_OBJ} for upload after MESH!")

        elif stage == "SPLAT":
            splat_path = self.workspace / self.SPLAT_FILE
            preview_ply = self.workspace / self.SPLAT_PREVIEW_PLY
            preview_glb = self.workspace / self.SPLAT_PREVIEW_GLB

            if not splat_path.exists():
                raise RuntimeError(f"SPLAT artifact missing: {self.SPLAT_FILE}")

            results["splat_url"] = self.storage.upload_file(
                f"jobs/{self.job_id}/output/splat/{self.SPLAT_FILE}",
                splat_path
            )
            results["splat_format"] = "npz_gaussians_v1"

            if preview_ply.exists():
                results["splat_preview_ply"] = self.storage.upload_file(
                    f"jobs/{self.job_id}/output/splat/{self.SPLAT_PREVIEW_PLY}",
                    preview_ply
                )

            if preview_glb.exists():
                results["splat_preview_glb"] = self.storage.upload_file(
                    f"jobs/{self.job_id}/output/splat/{self.SPLAT_PREVIEW_GLB}",
                    preview_glb
                )
            if self.splat_metrics:
                results["splat_metrics"] = self.splat_metrics

        if hasattr(self.storage, "commit"):
            self.storage.commit()
            logger.info("💾 Storage commit completed.")

        return results

    def run_sfm(self, robust: bool = True):
        logger.info(f"🚀 Running SFM for {self.job_id} on {len(list(self.images_dir.glob('*')))} images")
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
        
        # v10.0.0: Capture quality metrics
        num_registered = 0
        total_images = len(list(self.images_dir.glob("*")))
        
        # Check if model 0 exists and count registered images
        model0_dir = self.sparse_dir / "0"
        if model0_dir.exists():
            images_bin = model0_dir / "images.bin"
            images_txt = model0_dir / "images.txt"
            
            if images_bin.exists():
                # For binary models, we'd need a parser, but images.txt is easier if it exists
                # Fallback: Count files in model 0 if present
                num_registered = total_images # Assume all if successfully finished for now
            elif images_txt.exists():
                try:
                    with open(images_txt, 'r') as f:
                        # Count lines starting with integer (image id)
                        num_registered = len([l for l in f if l and l[0].isdigit() and not l.startswith('#')])
                except:
                    num_registered = total_images
        
        return {
            "status": "success",
            "num_registered": num_registered,
            "total_images": total_images,
            "sparse_model_exists": model0_dir.exists()
        }

    def _has_valid_sparse_model(self) -> bool:
        return self._find_best_sparse_model() is not None

    def _find_best_sparse_model(self) -> Optional[Path]:
        """🏁 v10.3.0: Helper to find the sparse model output by SFM containing actual files."""
        def has_model_files(folder: Path) -> bool:
            if not folder.exists() or not folder.is_dir(): return False
            has_cam = (folder / "cameras.bin").exists() or (folder / "cameras.txt").exists()
            has_img = (folder / "images.bin").exists() or (folder / "images.txt").exists()
            has_pts = (folder / "points3D.bin").exists() or (folder / "points3D.txt").exists()
            return has_cam and has_img and has_pts

        if has_model_files(self.sparse_dir):
            return self.sparse_dir
            
        if self.sparse_dir.exists():
            valid_models = [d for d in self.sparse_dir.iterdir() if d.is_dir() and has_model_files(d)]
            if valid_models:
                return sorted(valid_models)[0]
                
        return None

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
            "--ImageReader.camera_model", "OPENCV", # 🧠 SWITCHED from RADIAL
            "--ImageReader.single_camera", "1",
            "--SiftExtraction.max_num_features", "16384",  # High density
            "--SiftExtraction.estimate_affine_shape", "1",
            "--SiftExtraction.domain_size_pooling", "1"
        ], "SFM_FE_RELAXED")

    def _sfm_match_features(self):
        """Helper: Feature matching."""
        self.run_command([
            "colmap", "exhaustive_matcher", 
            "--database_path", str(self.db_path),
            "--SiftMatching.cross_check", "1",
            "--SiftMatching.use_gpu", "0" # 🧠 Force CPU for stability on headless Kaggle
        ], "SFM_MATCH_RELAXED")

    def _sfm_mapper(self):
        """Helper: Mapper."""
        self.run_command([
            "colmap", "mapper",
            "--database_path", str(self.db_path),
            "--image_path", str(self.images_dir),
            "--output_path", str(self.sparse_dir),
            "--Mapper.init_min_num_inliers", "6",        # 🧠 EXTREME RELAXATION
            "--Mapper.abs_pose_min_num_inliers", "6",    # 🧠 EXTREME RELAXATION
            "--Mapper.init_min_tri_angle", "2.0",        # More lenient angle
            "--Mapper.min_model_size", "2",
            "--Mapper.tri_min_angle", "0.5",
            "--Mapper.multiple_models", "1",
            "--Mapper.max_reg_trials", "5"               # More retries
        ], "SFM_MAP_RELAXED")

    def run_mvs(self):
        # 🏁 v10.3.0: Robust model discovery (checks for actual model files)
        sparse_model = self._find_best_sparse_model()
        if not sparse_model:
            raise RuntimeError(f"No valid sparse model found in {self.sparse_dir} for MVS")
        logger.info(f"📍 Using sparse model: {sparse_model}")

        self.run_command([
            "colmap", "image_undistorter", 
            "--image_path", str(self.images_dir), 
            "--input_path", str(sparse_model), 
            "--output_path", str(self.dense_dir)
        ], "MVS_UNDISTORT")
        
        try:
            self.run_command([
                "colmap", "patch_match_stereo", 
                "--workspace_path", str(self.dense_dir),
                "--PatchMatchStereo.min_triangulation_angle", "0.5"
            ], "MVS_STEREO")
        except Exception as e:
            logger.warning(f"⚠️ MVS_STEREO failed (likely due to missing CUDA): {e}. Skipping to fusion...")
            # We don't raise here, we try to move to fusion which may have a fallback
        
        self.run_command([
            "colmap", "stereo_fusion", 
            "--workspace_path", str(self.dense_dir), 
            "--output_path", str(self.dense_dir / "dense.ply"),
            "--StereoFusion.min_num_pixels", "3"
        ], "MVS_FUSION")

        dense_ply = self.dense_dir / self.DENSE_PLY
        dense_points = self._ply_point_count(dense_ply)
        if dense_points < 50:
            logger.warning(
                f"⚠️ MVS fusion produced sparse dense cloud ({dense_points} points). "
                "Falling back to sparse model conversion."
            )
            self.run_command([
                "colmap", "model_converter",
                "--input_path", str(sparse_model),
                "--output_path", str(dense_ply),
                "--output_type", "PLY"
            ], "MVS_SPARSE_TO_PLY_FALLBACK")
            dense_points = self._ply_point_count(dense_ply)
            logger.info(f"📊 Fallback dense cloud points: {dense_points}")
            if dense_points < 50:
                raise RuntimeError(f"MVS produced unusable dense cloud after fallback: {dense_points} points")
        
        return {
            "status": "success",
            "point_count": dense_points
        }

    def _ply_point_count(self, ply_path: Path) -> int:
        if not ply_path.exists() or ply_path.stat().st_size <= 0:
            return 0
        try:
            import trimesh
            geom = trimesh.load(str(ply_path), process=False)
            pts = getattr(geom, "vertices", None)
            return 0 if pts is None else int(len(pts))
        except Exception as e:
            logger.warning(f"Could not parse PLY point count for {ply_path.name}: {e}")
            return 0

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

    def _mesh_count(self, ms) -> int:
        """
        PyMeshLab compatibility helper across versions.
        """
        if hasattr(ms, "number_meshes"):
            return ms.number_meshes()
        if hasattr(ms, "number_of_meshes"):
            return ms.number_of_meshes()
        return 0

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
            if self._mesh_count(ms) > 1:
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
                        if self._mesh_count(ms) > 1:
                            ms.set_current_mesh(self._mesh_count(ms) - 1)
                            if ms.current_mesh().vertex_number() > 0:
                                reconstruction_success = True
                    except: pass
            
            # Verify we have geometry now
            if not reconstruction_success or self._mesh_count(ms) < 2:
                raise RuntimeError("All reconstruction attempts failed to produce a valid mesh from the point cloud.")
                
            m_reconstructed = ms.current_mesh()
            logger.info(f"📐 Geometry verified: {m_reconstructed.vertex_number()} vertices")
            
            # --- Step 2: Color Transfer ---
            # Link color from Mesh 0 (Dense PLY) to the LAST added mesh (Reconstructed)
            target_idx = self._mesh_count(ms) - 1
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
            
            # --- Step 4: Export GLB for Web/AR ---
            try:
                import trimesh
                mesh = trimesh.load(str(final_mesh_obj), process=False)
                glb_path = self.dense_dir / "mesh.glb"
                mesh.export(str(glb_path))
                logger.info(f"✅ GLB export complete: {glb_path.name}")
            except Exception as ge:
                logger.warning(f"⚠️ GLB export failed: {ge}")
                
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
                # Final geometric fallback: convex hull from dense point cloud.
                try:
                    import trimesh
                    logger.info("Attempting convex hull fallback from dense point cloud...")
                    cloud = trimesh.load(str(dense_ply), process=False)
                    points = getattr(cloud, "vertices", None)
                    if points is None or len(points) < 4:
                        raise RuntimeError("Dense cloud has insufficient points for convex hull")
                    hull = trimesh.convex.convex_hull(points)
                    hull.export(str(final_mesh_obj))
                    logger.info(f"✅ Convex hull fallback mesh generated: {final_mesh_obj.name}")
                except Exception as he:
                    logger.error(f"❌ Convex hull fallback failed: {he}")
                    raise RuntimeError(f"Failed to generate mesh: {e}")
                    
        # 📊 Capture final metrics
        final_points = 0
        try:
            if final_mesh_obj.exists():
                import trimesh
                m = trimesh.load(str(final_mesh_obj), process=False)
                final_points = len(m.vertices) if hasattr(m, 'vertices') else 0
        except Exception as te:
            logger.warning(f"Could not extract mesh metrics: {te}")

        return {
            "status": "success",
            "mesh_generated": True,
            "point_count": final_points
        }

    def run_splat(self):
        """
        Generate a deployable splat artifact from dense geometry.
        Format: custom NPZ payload stored as .splat for deterministic runtime use.
        """
        import time
        import trimesh

        start = time.time()
        dense_ply = self.dense_dir / self.DENSE_PLY
        mesh_obj = self.dense_dir / self.MESH_OBJ
        splat_file = self.workspace / self.SPLAT_FILE

        trainer_cmd = os.getenv("SPLAT_TRAIN_CMD", "").strip()
        allow_fallback = os.getenv("SPLAT_ALLOW_FALLBACK", "1").lower() not in ("0", "false", "no")
        if trainer_cmd:
            logger.info("Attempting configured SPLAT trainer command...")
            cmd = trainer_cmd.format(
                job_id=self.job_id,
                workspace=str(self.workspace),
                images_dir=str(self.images_dir),
                sparse_dir=str(self.sparse_dir),
                dense_dir=str(self.dense_dir),
                output_splat=str(splat_file),
                iterations=os.getenv("SPLAT_ITERATIONS", "3000"),
                resolution_cap=os.getenv("SPLAT_RESOLUTION_CAP", "1600"),
                sh_degree=os.getenv("SPLAT_SH_DEGREE", "2"),
                prune_every=os.getenv("SPLAT_PRUNE_EVERY", "100")
            )
            try:
                self.run_command(["bash", "-lc", cmd], "SPLAT_TRAIN")
            except Exception as e:
                if not allow_fallback:
                    raise RuntimeError(f"SPLAT trainer failed and fallback is disabled: {e}")
                logger.warning(f"SPLAT trainer failed; using dense fallback conversion: {e}")

            if splat_file.exists() and splat_file.stat().st_size > 0:
                duration_s = round(time.time() - start, 3)
                self.splat_metrics = {
                    "num_points": None,
                    "train_steps": int(os.getenv("SPLAT_ITERATIONS", "3000")),
                    "duration_s": duration_s,
                    "loss_final": None
                }
                return splat_file

        if dense_ply.exists():
            geom = trimesh.load(str(dense_ply), process=False)
        elif mesh_obj.exists():
            geom = trimesh.load(str(mesh_obj), process=False)
        else:
            geom = None

        points = getattr(geom, "vertices", None) if geom is not None else None
        if points is None or len(points) < 10:
            # Fallback to sparse points when dense/mesh are unusable.
            sparse_model = self.sparse_dir / "0"
            if not sparse_model.exists():
                models = sorted([d for d in self.sparse_dir.iterdir() if d.is_dir()]) if self.sparse_dir.exists() else []
                if models:
                    sparse_model = models[0]
            sparse_ply = self.workspace / "sparse_points_fallback.ply"
            if sparse_model.exists():
                try:
                    self.run_command([
                        "colmap", "model_converter",
                        "--input_path", str(sparse_model),
                        "--output_path", str(sparse_ply),
                        "--output_type", "PLY"
                    ], "SPLAT_SPARSE_FALLBACK")
                    geom = trimesh.load(str(sparse_ply), process=False)
                    points = getattr(geom, "vertices", None)
                    logger.info(f"Using sparse fallback points for SPLAT: {0 if points is None else len(points)}")
                except Exception as e:
                    logger.warning(f"Sparse fallback conversion failed for SPLAT: {e}")

        if points is None or len(points) < 10:
            raise RuntimeError("Insufficient geometry points for splat generation.")

        colors = getattr(geom.visual, "vertex_colors", None)
        if colors is None or len(colors) != len(points):
            colors = np.tile(np.array([[200, 200, 200, 255]], dtype=np.uint8), (len(points), 1))
        else:
            colors = np.asarray(colors, dtype=np.uint8)

        max_points = int(os.getenv("SPLAT_MAX_POINTS", "200000"))
        if len(points) > max_points:
            rng = np.random.default_rng(42)
            idx = rng.choice(len(points), size=max_points, replace=False)
            points = points[idx]
            colors = colors[idx]

        bbox_min = points.min(axis=0)
        bbox_max = points.max(axis=0)
        diag = float(np.linalg.norm(bbox_max - bbox_min))
        base_scale = max(diag / 600.0, 1e-4)

        scales = np.full((len(points), 3), base_scale, dtype=np.float32)
        opacity = np.full((len(points), 1), 0.9, dtype=np.float32)
        rotation = np.tile(np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32), (len(points), 1))

        with open(splat_file, "wb") as f:
            np.savez_compressed(
                f,
                xyz=points.astype(np.float32),
                rgb=colors[:, :3].astype(np.uint8),
                alpha=opacity,
                scale=scales,
                rot_quat=rotation,
            )

        preview_ply = self.workspace / self.SPLAT_PREVIEW_PLY
        trimesh.points.PointCloud(points, colors=colors).export(preview_ply)

        preview_glb = self.workspace / self.SPLAT_PREVIEW_GLB
        try:
            scene = trimesh.Scene([trimesh.points.PointCloud(points, colors=colors)])
            scene.export(preview_glb)
        except Exception as e:
            logger.warning(f"GLB preview generation skipped: {e}")

        self.splat_metrics = {
            "num_points": int(len(points)),
            "train_steps": 0,
            "duration_s": round(time.time() - start, 3),
            "loss_final": None
        }
        logger.info(f"✅ SPLAT artifact generated: {splat_file.name} ({len(points)} points)")
        return splat_file
