# Morphic 3D Scanner - Scaling Roadmap

This document outlines the strategic technical path to evolve Morphic from a small-object photogrammetry tool into a full-scale room and "dollhouse" scanning solution.

## 1. High-Fidelity Rendering: Gaussian Splatting (3DGS)
To achieve realistic room captures, we will transition from traditional meshes to 3D Gaussian Splatting.
- **Goal**: Real-time, photorealistic rendering of complex environments.
- **Integration**:
    - [x] Use COLMAP for SfM via **Modal Cloud Worker** ([modal_colmap.py](file:///home/harpreet/Documents/3d_scanner/gpu_worker/modal_colmap.py)) to bypass local RAM limits.
    - [ ] Implement a training pipeline using `gsplat` or `nerfstudio`.
    - [ ] Deploy a web-based Gaussian Splat viewer (e.g., using Three.js or specialized GS viewers).

## 2. Cinematic Captures: NeRF (Neural Radiance Fields)
For high-end cinematic captures and novel view synthesis where traditional geometry fails (reflections, thin structures).
- **Goal**: Provide cinematic "fly-through" videos of scanned rooms.
- **Integration**:
    - Integration with `Instant-NGP` or `Nerfacto` for fast training.
    - Exporting high-resolution video trajectories.

## 3. Distributed Processing Pipeline
Room-scale scans require processing 500-2000+ images, which is too much for a single worker.
- **Goal**: Scalable backend capable of handling massive datasets.
- **Strategy**:
    - **Task Queues**: Implement Celery with Redis/RabbitMQ for horizontal scaling.
    - **Compute Clusters**: Ability to spin up GPU-enabled cloud instances (AWS EC2 G5, Lambda Labs) dynamically.
    - **Chunked SfM**: For very large rooms, use Hierarchical SfM to split the scene into manageable chunks.

## 4. Mobile AR Integration
Providing users with real-time feedback during the scanning process.
- **Goal**: Better "UX" for room scanning and faster reconstruction.
- **Integration**:
    - **ARKit/ARCore**: Capture initial camera poses and sparse depth maps on the mobile device.
    - **Pose Injection**: Upload AR-source poses to COLMAP to skip/assist the exhaustive matching phase, reducing processing time by 50-70%.
    - **Room Layouts**: Use mobile LIDAR (iPhone Pro) to capture "room-plan" boundaries for the dollhouse effect.

## 5. The "Dollhouse" Effect
Transforming room scans into navigable 3D floor plans.
- **Goal**: Automatic floor plan and wall extraction.
- **Technology**:
    - **Plane Fitting**: Use RANSAC-based plane detection in point clouds to identify walls and floors.
    - **Semantics**: Integrate SAM (Segment Anything Model) or Mask R-CNN to identify furniture and architectural elements.
