from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.api import scans, workers
import os

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

@app.get("/")
async def read_index():
    return FileResponse('frontend/index.html')
