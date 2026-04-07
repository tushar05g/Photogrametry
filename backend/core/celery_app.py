import os
import logging
from celery import Celery
from backend.config import settings

logger = logging.getLogger(__name__)

# 🏁 v4.0.0: Production-Grade Celery Configuration
celery_app = Celery(
    "photogrammetry_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=7200,  # 2 hours max per job
    task_soft_time_limit=3600, # 1 hour soft limit
    # Task Routing
    task_routes={
        "worker.pipeline.tasks.run_pipeline": {"queue": "gpu_tasks"},
        "worker.pipeline.tasks.preprocess_only": {"queue": "cpu_tasks"}
    }
)

# 📂 Task Auto-Discovery
celery_app.autodiscover_tasks(['worker.pipeline'], force=True)
