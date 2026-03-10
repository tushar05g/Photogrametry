# 🛰️ Morphic 3D Scanner (v3.0)

A high-performance, distributed 3D scanning platform using **Gaussian Splatting** (Nerfstudio/splatfacto) for photorealistic 3D reconstruction. This version (v3.0) is optimized for speed, reliability, and production-grade stability on Kaggle GPU environments.

---

## 🚀 Key Features (v3.0 Optimizations)

- **100x Faster Polling**: Switched from HTTP polling to a high-speed **Redis Queue** system.
- **4-10x Processing Speedup**: Implemented parallel image masking using `ThreadPoolExecutor`.
- **9x Repeat Job Speedup**: Intelligent image and COLMAP result caching.
- **Fail-Fast Reliability**: Strict 'masking-or-abort' policy to prevent corrupted 3D models.
- **Legacy Stable Stack**: Custom dependency pins (NumPy 1.26.4 / Python 3.12) to solve binary compatibility on Kaggle.

---

## 🏗️ Architecture

- **Backend (FastAPI)**: Manages jobs, workers, and results. Uses SQLAlchemy with connection pooling and Redis for the job queue.
- **Worker (Kaggle/GPU)**: Distributed Python workers that perform the heavy lifting (COLMAP + Nerfstudio).
- **Frontend (Three.js)**: Modern web viewer for interactive 3D model visualization.
- **Storage (Cloudinary)**: Secure, scalable hosting for generated `.ply` and `.glb` models.

---

## 🛠️ Quick Start (Local Setup)

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Cloudinary Account (for 3D hosting)
- Ngrok (for local development tunnel)

### 2. Configure Environment
Create a `.env` file from the example:
```bash
cp .env.example .env
```
Update with your credentials (Cloudinary, Database, Ngrok URL).

### 3. Launch Services
```bash
docker compose up --build
```
The backend includes an automatic migration runner using Alembic.

---

## 🛰️ Deploying GPU Worker (Kaggle)

1. Create a new **Kaggle Notebook** with GPU T4 x2 enabled.
2. Copy the contents of `scripts/kaggle_worker.py` into a cell.
3. Configure your `BACKEND_URL` (Ngrok) and `WORKER_ID` at the top of the script.
4. Run the cell. The worker will automatically:
   - Purge conflicting NumPy 2.x binaries.
   - Install the **Legacy Stable** stack for Python 3.12 compatibility.
   - Begin listening for jobs from your Redis queue.

---

## 🧪 Testing and Quality

- **Unit Tests**: Full suite for queue, cache, and DB pooling in `tests/test_optimizations.py`.
- **Health Checks**: Monitor system status at `GET /health`.
- **Logs**: Backend logs are stored in `logs/backend.log`.

---

## 📜 Development & Contributions

```bash
# Install in development mode
pip install -e .

# Run the test suite
pytest tests/test_optimizations.py

# Style guide
flake8 backend/ scripts/
```

Developed with ❤️ for the 3D scanning community.