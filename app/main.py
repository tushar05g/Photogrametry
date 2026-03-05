from fastapi import FastAPI
from app.routes import scans

app = FastAPI()
app.include_router(scans.router, prefix="/scans")
