import os
import uvicorn
import logging
import asyncio
import redis.asyncio as redis
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import upload, scans, worker_api
from backend.config import settings
from backend.core.db import engine, Base
from backend.core.observability import setup_logging
from backend.websocket.manager import manager

# 🔍 Initialize Advanced Structured Logging (v8.1.0)
setup_logging()
logger = logging.getLogger(__name__)

# 🗄️ Database Initialization
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="9.0.0",
    description="Distributed Photogrammetry Pipeline with Neon DB and Storage Abstraction."
)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Backend starting on http://localhost:8000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- API Routers (MUST be registered before catch-all) ---
app.include_router(upload.router, prefix=f"{settings.API_V1_STR}/jobs", tags=["Upload"])
app.include_router(scans.router, prefix=f"{settings.API_V1_STR}/scans", tags=["Status"])
app.include_router(worker_api.router, prefix=settings.API_V1_STR, tags=["Worker API"])

# --- Static Files ---
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# --- Legacy Redirects (for cached frontend clients) ---
from fastapi.responses import RedirectResponse

@app.get("/scans/")
async def legacy_list_scans():
    return RedirectResponse(url="/api/v1/scans/all")

@app.get("/scans/{job_id}/progress")
async def legacy_job_progress(job_id: str):
    return RedirectResponse(url=f"/api/v1/scans/{job_id}/progress")

@app.post("/scans/{job_id}/cancel")
async def legacy_job_cancel(job_id: str):
    return RedirectResponse(url=f"/api/v1/scans/{job_id}/cancel")

# --- Explicit Routes ---
@app.get("/")
async def serve_frontend():
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health_check():
    return {"status": "online", "version": "9.0.0", "storage": settings.STORAGE_TYPE}

# 🔌 WebSocket & Redis Pub/Sub Hybrid
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(websocket, job_id)
    
    r = redis.from_url(settings.REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"job_status:{job_id}")
    
    async def listen_to_redis():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"].decode("utf-8")
                    import json
                    await websocket.send_json(json.loads(data))
        except Exception as e:
            logger.error(f"Redis listen error: {e}")

    listener_task = asyncio.create_task(listen_to_redis())
    
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
        listener_task.cancel()
        await pubsub.unsubscribe(f"job_status:{job_id}")

# 🌐 Catch-All SPA Route (MUST BE LAST — after all API routes)
@app.get("/{path:path}")
async def catch_all(path: str):
    if path.startswith("api/") or path == "health" or path.startswith("ws/"):
        raise HTTPException(status_code=404, detail="Not Found")
    
    file_path = Path("frontend") / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True, reload_dirs=["backend", "shared", "worker"])
