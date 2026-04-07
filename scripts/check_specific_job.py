from sqlalchemy import create_engine, text
from backend.config import settings
import sys

job_id = sys.argv[1]
engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text(f"SELECT job_id, project_name, status, current_stage, progress FROM jobs WHERE job_id = '{job_id}'"))
    row = result.first()
    if row:
        print(f"ID: {row[0]} | Project: {row[1]} | Status: {row[2]} | Stage: {row[3]} | Progress: {row[4]}%")
    else:
        print("Job not found.")
