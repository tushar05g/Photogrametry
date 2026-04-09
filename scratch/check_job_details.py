
import os
import json
import asyncio
from sqlalchemy import create_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_bchJ2Ud0WwBz@ep-quiet-recipe-aipung0n-pooler.c-4.us-east-1.aws.neon.tech/neondb?ssl=require"

async def get_job_details(job_id):
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(text("SELECT id, job_id, project_name, status, current_stage, error_message, quality_report FROM scan_jobs WHERE job_id = :job_id"), {"job_id": job_id})
        row = result.fetchone()
        if row:
            # Row is (id, job_id, project_name, status, current_stage, error_message, quality_report)
            data = {
                "id": row[0],
                "job_id": row[1],
                "project_name": row[2],
                "status": row[3],
                "current_stage": row[4],
                "error_message": row[5],
                "quality_report": row[6]
            }
            print(json.dumps(data, indent=2, default=str))
        else:
            print(f"Job {job_id} not found")
    
    await engine.dispose()

if __name__ == "__main__":
    job_id = "d8927445-d482-440d-84b2-6403d7421a7a"
    asyncio.run(get_job_details(job_id))
