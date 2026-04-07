from sqlalchemy import create_engine, text
from backend.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    result = conn.execute(text("SELECT job_id, project_name, status, current_stage, progress FROM jobs ORDER BY created_at DESC LIMIT 10;"))
    rows = result.all()
    for row in rows:
        print(f"ID: {row[0]} | Project: {row[1]} | Status: {row[2]} | Stage: {row[3]} | Progress: {row[4]}%")
