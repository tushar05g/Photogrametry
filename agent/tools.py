import os
import sys
from datetime import datetime
from typing import List, Optional
import uuid

# Add the project root to the path so we can import backend/core etc.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.db import SessionLocal
from backend.models.models import ScanJob, JobStatus, ScanImage
from sqlalchemy import desc

def get_system_status() -> str:
    """
    Summarizes the current state of all scan jobs.
    Returns a human-readable string for the agent to use.
    """
    db = SessionLocal()
    try:
        # Get count of jobs by status
        total_jobs = db.query(ScanJob).count()
        pending = db.query(ScanJob).filter(ScanJob.status == JobStatus.pending).count()
        processing = db.query(ScanJob).filter(ScanJob.status == JobStatus.processing).count()
        failed = db.query(ScanJob).filter(ScanJob.status == JobStatus.failed).count()
        completed = db.query(ScanJob).filter(ScanJob.status == JobStatus.completed).count()

        summary = (
            f"📊 **System Status Update** ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n"
            f"- Total Scans: {total_jobs}\n"
            f"- Pending ⏳: {pending}\n"
            f"- Processing ⚙️: {processing}\n"
            f"- Completed ✅: {completed}\n"
            f"- Failed ❌: {failed}\n"
        )
        
        if processing > 0:
            active_jobs = db.query(ScanJob).filter(ScanJob.status == JobStatus.processing).all()
            summary += "\n**Active Jobs:**\n"
            for job in active_jobs:
                summary += f"- `{str(job.id)[:8]}`: {job.project_name} ({job.progress or 'starting...'})\n"
                
        return summary
    finally:
        db.close()

def diagnose_job_failure(job_id_str: str) -> str:
    """
    Analyzes a failed job and provides a diagnosis.
    """
    db = SessionLocal()
    try:
        job_id = uuid.UUID(job_id_str)
        job = db.query(ScanJob).filter(ScanJob.id == job_id).first()
        
        if not job:
            return f"❌ Job `{job_id_str}` not found."
            
        if job.status != JobStatus.failed:
            return f"ℹ️ Job `{job_id_str}` is currently `{job.status.value}`, not failed."
            
        diagnosis = f"🔍 **Failure Diagnosis for `{job.project_name}`**\n"
        diagnosis += f"- Job ID: `{job_id}`\n"
        diagnosis += f"- Error Message: `{job.error_message or 'No specific error recorded'}`\n"
        
        # Analyze common failure patterns based on error message
        err = (job.error_message or "").lower()
        if "colmap" in err:
            diagnosis += "\n💡 **AI Suggestion**: The reconstruction failed during the SfM (Structure from Motion) stage. This usually means there isn't enough overlap between your photos, or the images are too blurry for feature matching."
        elif "cloudinary" in err:
            diagnosis += "\n💡 **AI Suggestion**: There was a network issue uploading or downloading images. Check your internet connection or Cloudinary credentials."
        elif "out of memory" in err or "oom" in err:
            diagnosis += "\n💡 **AI Suggestion**: The worker ran out of RAM or VRAM. Try uploading fewer or smaller images (max 20 recommended)."
        else:
            diagnosis += "\n💡 **AI Suggestion**: This is an unknown failure. I recommend checking the raw logs on the worker node for more details."
            
        return diagnosis
    except ValueError:
        return "❌ Invalid Job ID format. Please provide a full UUID."
    finally:
        db.close()

def list_recent_jobs(limit: int = 5) -> str:
    """
    Lists the last few jobs for quick overview.
    """
    db = SessionLocal()
    try:
        jobs = db.query(ScanJob).order_by(desc(ScanJob.created_at)).limit(limit).all()
        if not jobs:
            return "No jobs found in the database."
            
        summary = f"🕒 **Last {len(jobs)} Jobs:**\n"
        for job in jobs:
            status_emoji = {
                JobStatus.completed: "✅",
                JobStatus.failed: "❌",
                JobStatus.processing: "⚙️",
                JobStatus.pending: "⏳",
                JobStatus.cancelled: "🚫",
                JobStatus.uploading: "☁️",
                JobStatus.initializing: "🆕"
            }.get(job.status, "❓")
            
            summary += f"- {status_emoji} `{str(job.id)[:8]}` | {job.project_name} | {job.status.value}\n"
            
        return summary
    finally:
        db.close()

if __name__ == "__main__":
    # Quick test
    print(get_system_status())
    print("\n" + list_recent_jobs())
