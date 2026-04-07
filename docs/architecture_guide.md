# Senior Developer's Guide: Serverless Cloud Photogrammetry (v6.0.0)

Welcome to the definitive architecture of the **3D Scanner Cloud Engine**. This document explains how we transformed a compute-intensive, memory-heavy photogrammetry task into a scalable, serverless pipeline.

---

## 1. 🏗️ High-Level Topology

The project is built on a **Decoupled Architecture**. This means the "Brain" (API) and the "Muscle" (GPU) are completely separate, allowing them to scale independently.

- **Frontend**: Three.js + Vanilla JS (The Viewer).
- **Brain**: FastAPI (Python) - Manages jobs, authenticates uploads, and coordinates state.
- **Broker**: Redis + Celery - A "Waitlist" that holds tasks until a worker is ready.
- **Muscle**: Modal (Cloud GPU) - On-demand A10G instances that spawn only when needed.
- **Storage**: Modal Volume (`morphic-scan-data`) - A shared, cloud-native filesystem.

---

## 2. 🔄 The 4-Stage Lifecycle

### Stage A: The Async Handshake (Upload)
When you upload 18 images, the FastAPI backend doesn't wait for the cloud volume to finish writing. It uses **Asynchronous I/O**.
> [!NOTE]
> **Teacher Note**: Standard Python `open()` blocks the entire server. If 5 people upload at once, the server hangs. We use `await storage_service.save_file` to let the server handle other users while the upload is "in flight."

### Stage B: The Message Broker (Orchestration)
The API creates a "Message" and sends it to **Redis**. The **Celery Worker** picks up this message and calls `modal.Function.from_name("photogrammetry").spawn()`.
- **Senior Dev Insight**: We use `spawn()` (async) so the Celery worker stays free to manage *other* jobs while the Cloud GPU is warming up.

### Stage C: Cloud Compute (A10G GPU)
The Modal worker starts. It doesn't have your images yet! It **mounts** the `morphic-scan-data` volume. To the worker, this volume looks like a local hard drive (`/data`).
- **Lesson**: This is "Local-Performance Cloud Storage."

### Stage D: Native Consistency (The Volume)
As COLMAP generates the `sparse` and `dense` models, it writes directly back to the volume.
- **Teacher Note**: We use **Volumes** instead of **S3** because COLMAP does thousands of "Random Access" reads/writes. S3 is designed for large, sequential files. Using a Volume makes SfM (Structure from Motion) up to 10x faster.

---

## 3. 🎓 Senior Teacher Notes

### 🧐 Why "Offscreen" Rendering?
In `modal_app.py`, we set `QT_QPA_PLATFORM=offscreen`. 
**Why?** COLMAP's `dense_reconstructor` often tries to open a GUI window to show progress. Since cloud servers have no monitors (Headless), COLMAP would crash instantly. This environment variable tells COLMAP: *"Pretend there is a monitor; just draw to memory."*

### 🧐 Why a "Status.json" over a database?
The Cloud Worker doesn't have direct access to your local MySQL/SQLite DB. Instead, it writes its progress to a `status.json` file in the volume.
**Teacher Note**: This is called **Decoupled State**. The API simply "Polls" the volume for this file. This makes the worker completely independent and easier to test.

### 🧐 The "Path Validation" Trap
In Modal 1.x, you cannot pass complex `PosixPath` objects between your laptop and the cloud. 
**Senior Lesson**: Always pass **Primitive Types** (Strings, Integers) across the network. This is why we refactored the `config.py` to use string literals for storage paths.

---

## 🏁 Final Stability Checklist
> [!TIP]
> Now that the legacy `gpu_worker/` and `core/` files are removed, your project follows the **Standard FastAPI Service Pattern**:
> 1. `backend/routes`: Handlers.
> 2. `backend/services`: Logic.
> 3. `modal_worker`: Cloud Spec.
> 4. `shared/schemas`: Universal communication.

**Happy Coding, Senior.** 🏆
