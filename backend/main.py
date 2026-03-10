from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import scans, workers
import os
import logging
from datetime import datetime

# 🎓 TEACHER'S NOTE: Set up logging so you can see what's happening in production.
# Logs help you debug issues and monitor your app's health.
import os
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/backend.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

def validate_environment():
    """Validate required environment variables on startup."""
    from backend.core.config import DATABASE_URL, CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, REDIS_URL
    
    # Check for missing values in the config module directly
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise RuntimeError("Missing required Cloudinary environment variables in .env")
    
    # Validate database connection
    try:
        from backend.core.db import get_db
        db = next(get_db())
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        logger.info("✅ Database connection validated")
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")
    
    # Validate Redis connection
    try:
        import redis
        r = redis.from_url(REDIS_URL)
        r.ping()
        logger.info("✅ Redis connection validated")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection check failed (is it running?): {e}")

    logger.info("✅ Environment validation passed")

# Run validation on import
validate_environment()

# 🎓 TEACHER'S NOTE: This is the "heart" of your 3D scanner app!
app = FastAPI(title="Morphic 3D Scanner API", version="3.0.0")

# Register all route groups
app.include_router(scans.router, prefix="/scans", tags=["Scans"])
app.include_router(workers.router, prefix="/workers", tags=["Workers"])

# Mount frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 🛡️ CORS Middleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🛡️ Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')

@app.get("/health")
async def health_check():
    """Health check endpoint for worker verification and system monitoring."""
    from backend.core.config import REDIS_URL
    import redis
    try:
        r = redis.from_url(REDIS_URL)
        r.ping()
        redis_ok = True
    except Exception as e:
        redis_ok = False
        logger.warning(f"Redis health check failed: {e}")
    
    return {
        "status": "ok",
        "version": "3.0",
        "redis": "ok" if redis_ok else "error",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/scans/{job_id}/progress")
async def get_job_progress(job_id: str):
    """Get real-time progress for a job."""
    from backend.core.db import get_db
    from backend.models.models import ScanJob
    db = next(get_db())
    job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
    if not job:
        return {"error": "Job not found"}
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": getattr(job, 'progress', 0),
        "warnings": getattr(job, 'warnings', ''),
        "error_message": getattr(job, 'error_message', ''),
        "model_url": job.model_url,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None
    }
