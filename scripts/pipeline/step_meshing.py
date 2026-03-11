import os
import pymeshlab
import trimesh
import logging

logger = logging.getLogger("worker")

class MeshingStep:
    def execute(self, ply_path, workspace):
        obj = os.path.join(workspace, "mesh.obj")
        glb = os.path.join(workspace, "model.glb")

        try:
            logger.info("🕸️ Running Screened Poisson Reconstruction...")
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(ply_path)
            ms.compute_normal_for_point_clouds()
            ms.generate_surface_reconstruction_screened_poisson()
            ms.save_current_mesh(obj)

            logger.info("🕸️ Exporting to GLB...")
            mesh = trimesh.load(obj)
            mesh.export(glb)
            return glb
        except Exception as e:
            logger.error(f"❌ Mesh conversion failed: {e}")
            # FALLBACK: Try to export the raw points as GLB
            try:
                logger.info("🔄 Fallback: Exporting raw points as GLB...")
                pts = trimesh.load(ply_path)
                pts.export(glb)
                return glb
            except:
                return None
