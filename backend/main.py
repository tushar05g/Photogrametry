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
    required = ["DATABASE_URL", "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    
    # Validate database connection
    try:
        from backend.core.db import get_db
        db = next(get_db())
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        logger.info("✅ Database connection validated")
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")
    
    logger.info("✅ Environment validation passed")

# Run validation on import
validate_environment()

# 🎓 TEACHER'S NOTE: This is the "heart" of your 3D scanner app!
# FastAPI is like Flask but with automatic API docs, type checking, and async support.
# 
# WHAT THIS FILE DOES:
# - Creates the main FastAPI app instance.
# - Registers all your API routes (endpoints) from scans.py and workers.py.
# - Serves your frontend HTML/JS files as static files.
# - Adds security middleware (CORS) so your frontend can talk to the API.
# 
# WHY FASTAPI? It's fast, has great docs, and catches bugs before they happen.

app = FastAPI(title="Morphic 3D Scanner API", version="2.0.0")

#🎓 Register all route groups ("routers")
# Each router is a mini-app responsible for one area of functionality.
app.include_router(scans.router, prefix="/scans", tags=["Scans"])
app.include_router(workers.router, prefix="/workers", tags=["Workers"])

# Mount the entire frontend folder so we can serve any future css/js files inside it
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# 🛡️ CORS Middleware: Required for cross-domain frontends (e.g. hosting on Vercel/Netlify)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you should replace "*" with specific domains
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
    import redis
    try:
        r = redis.Redis(host='scanner_redis', port=6379, db=0)
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
