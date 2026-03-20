import open3d as o3d
import sys
import numpy as np

def analyze_points(pcd_path):
    pcd = o3d.io.read_point_cloud(pcd_path)
    points = np.asarray(pcd.points)
    
    if len(points) == 0:
        print("Error: No points found in point cloud.")
        return

    print(f"Total Points: {len(points)}")
    
    # Check bounding box
    bbox = pcd.get_axis_aligned_bounding_box()
    extent = bbox.get_extent()
    print(f"Bounding Box Extent: {extent}")
    print(f"Ratios: {extent[0]/extent[1]:.2f}, {extent[1]/extent[2]:.2f}, {extent[0]/extent[2]:.2f}")
    
    # For a cube, the ratios should be close to 1:1:1
    
    # Check for clusters/outliers
    pcd_clean, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    print(f"Points after outlier removal: {len(pcd_clean.points)}")
    
    # Check planarity (RANSAC)
    try:
        plane_model, inliers = pcd.segment_plane(distance_threshold=0.01, ransac_n=3, num_iterations=1000)
        print(f"Largest plane inliers: {len(inliers)} ({len(inliers)/len(points)*100:.1f}%)")
    except:
        print("Could not segment plane.")

if __name__ == "__main__":
    analyze_points(sys.argv[1])
