import os
from sqlalchemy import create_engine, select, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ No DATABASE_URL found")
    exit(1)

engine = create_engine(DATABASE_URL)

def check_jobs():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT job_id, status, current_stage, created_at FROM jobs ORDER BY created_at DESC LIMIT 10"))
        for row in result:
            print(f"ID: {row[0]} | Status: {row[1]} | Stage: {row[2]} | Created: {row[3]}")

if __name__ == "__main__":
    check_jobs()
