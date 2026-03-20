"""
Meshing Step - Convert point cloud to GLB mesh
"""

import os
import trimesh
import pymeshlab
import logging
import glob
import subprocess

logger = logging.getLogger(__name__)

class MeshingStep:
    def execute(self, input_path, workspace):
        """Convert PLY or sparse points to GLB mesh."""
        try:
            # Find PLY file
            if os.path.isdir(input_path):
                # Look for PLY in sparse directory
                ply_files = glob.glob(os.path.join(input_path, "*.ply"))
                if not ply_files:
                    # Try to convert COLMAP binary
                    ply_path = os.path.join(workspace, "points.ply")
                    subprocess.run([
                        "colmap", "model_converter",
                        "--input_path", input_path,
                        "--output_path", ply_path,
                        "--output_type", "PLY"
                    ], check=True)
                    input_file = ply_path
                else:
                    input_file = ply_files[0]
            else:
                input_file = input_path
            
            glb_path = os.path.join(workspace, "model.glb")
            
            # Try mesh reconstruction
            try:
                logger.info("Creating mesh with Poisson reconstruction...")
                ms = pymeshlab.MeshSet()
                ms.load_new_mesh(input_file)
                ms.compute_normal_for_point_clouds()
                ms.generate_surface_reconstruction_screened_poisson(depth=6)
                ms.save_current_mesh(os.path.join(workspace, "temp.obj"))
                
                mesh = trimesh.load(os.path.join(workspace, "temp.obj"))
                mesh.export(glb_path)
                
            except Exception as e:
                logger.warning(f"Mesh reconstruction failed: {e}")
                # Fallback to point cloud
                logger.info("Exporting point cloud as GLB...")
                points = trimesh.load(input_file)
                if hasattr(points, 'vertices'):
                    point_mesh = trimesh.points.PointCloud(points.vertices)
                    scene = trimesh.Scene(point_mesh)
                    scene.export(glb_path)
                else:
                    raise RuntimeError("Cannot create 3D model")
            
            return glb_path
            
        except Exception as e:
            logger.error(f"Meshing failed: {e}")
            return None
