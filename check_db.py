import os
from app.db import SessionLocal
from app.models import ScanJob

db = SessionLocal()
jobs = db.query(ScanJob).order_by(ScanJob.created_at.desc()).limit(5).all()
for j in jobs:
    print(f"ID: {j.id}, Status: {j.status}, URL: {j.model_url}")
