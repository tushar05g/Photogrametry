import os
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MESH_LOCAL")

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

try:
    import pymeshlab
except ImportError:
    logger.error("❌ pymeshlab not found. Please run 'pip install pymeshlab'")
    sys.exit(1)

def _find_pml_filter(ms, keyword: str) -> str:
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

def test_meshing():
    dense_ply = Path("src/storage/bf8855eb/dense.ply")
    output_obj = Path("src/storage/bf8855eb/test_mesh.obj")
    
    if not dense_ply.exists():
        logger.error(f"❌ Could not find {dense_ply}")
        return

    logger.info(f"📐 Starting Local MESH test for {dense_ply}...")
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(dense_ply))
    m = ms.current_mesh()
    logger.info(f"📊 Input point cloud: {m.vertex_number()} vertices")

    # --- Step 0: Normals ---
    has_norms = False
    try:
        has_norms = getattr(m, 'has_vertex_normals', lambda: False)() or \
                    getattr(m, 'has_vertex_normal', lambda: False)()
    except: pass
    
    if not has_norms:
        logger.info("📐 Computing normals...")
        nf = _find_pml_filter(ms, "compute_normal_for_point_sets") or \
             _find_pml_filter(ms, "normal")
        if nf:
            logger.info(f"🔍 Using normal filter: {nf}")
            ms.apply_filter(nf, k=30)
        else:
            logger.warning("⚠️ No normal filter found!")

    # --- Step 1: Screened Poisson ---
    # EXCLUDE sampling and disk!
    pf = _find_pml_filter(ms, "screened_poisson") or \
         _find_pml_filter(ms, "surface_reconstruction") or \
         _find_pml_filter(ms, "poisson")
    
    if pf:
        logger.info(f"📐 Applying Reconstruction using filter: {pf}")
        # CHECK: Is this the sampling filter by mistake?
        if "sampling" in pf.lower() or "disk" in pf.lower():
            logger.error(f"❌ FAIL: Picked up wrong filter: {pf}")
            return

        try:
            if "poisson" in pf.lower():
                ms.apply_filter(pf, depth=8, samplespernode=1, pointweight=4)
            else:
                ms.apply_filter(pf)
        except Exception as e:
            logger.warning(f"⚠️ Poisson failed: {e}")

    # --- Step 1.5: Fallback ---
    m_curr = ms.current_mesh()
    if m_curr.vertex_number() == 0:
        logger.warning("🔄 Poisson produced 0 vertices. Attempting Ball Pivoting...")
        bpf = _find_pml_filter(ms, "ball_pivoting") or _find_pml_filter(ms, "reconstruction")
        if bpf:
            ms.set_current_mesh(0)
            ms.apply_filter(bpf)
            logger.info(f"🔄 Ball Pivoting success: {ms.current_mesh().vertex_number()} vertices")

    # --- Save ---
    ms.save_current_mesh(str(output_obj))
    logger.info(f"✅ Local test complete! Output saved to {output_obj}")
    logger.info(f"📊 Final result: {ms.current_mesh().vertex_number()} vertices")

if __name__ == "__main__":
    test_meshing()
