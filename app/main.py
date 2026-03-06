from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes import scans
import os

app = FastAPI()

# Include our scans router
app.include_router(scans.router, prefix="/scans")

# 🎓 TEACHER'S NOTE:
# This serves our simple HTML frontend at the root URL (/)
@app.get("/")
async def read_index():
    return FileResponse('app/static/index.html')
