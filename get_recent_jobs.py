import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    print("=== RECENT JOBS ===")
    res = conn.execute(text("SELECT job_id, status, current_stage, updated_at FROM jobs ORDER BY updated_at DESC LIMIT 5"))
    for row in res:
        print(f"Job: {row[0]} | Status: {row[1]} | Stage: {row[2]} | Updated: {row[3]}")
