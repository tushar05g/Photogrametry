import logging
import tempfile
import shutil
import io
import requests
from pathlib import Path
from celery import chain
from backend.core.celery_app import celery_app
from storage.factory import get_storage_provider
from shared.schemas import JobStatus, JobStage, StageStatus
from worker.pipeline.utils import (
    start_stage, 
    complete_stage, 
    fail_stage, 
    update_job_status, 
    is_stage_completed
)
from backend.config import settings

logger = logging.getLogger(__name__)

MODAL_ERROR_MSG = "Unknown error on Modal"

# 🏁 v9.0.0: Fully Abstracted & Resumable Pipeline

@celery_app.task(name="worker.pipeline.tasks.initiate_pipeline")
def initiate_pipeline(job_id: str, image_urls: list = None, enable_dense: bool = True, enable_splat: bool = False):
    """
    Orchestrates the granular tasks. If job already exists, picks up from where it left off.
    """
    logger.info(f"🚀 (Re)Initiating pipeline for job {job_id}")
    
    # 1. Start Job in DB
    update_job_status(job_id, status=JobStatus.IN_PROGRESS)
    
    # Define generic stage sequence with immutable signatures (.si) to avoid arg coupling
    stages = [
        (task_download.si(job_id, image_urls), JobStage.DOWNLOAD),
        (task_preprocess.si(job_id), JobStage.PREPROCESS),
        (task_sfm.si(job_id), JobStage.SFM)
    ]
    
    if enable_dense:
        stages.append((task_mvs.si(job_id), JobStage.MVS))
        stages.append((task_mesh.si(job_id), JobStage.MESH))
        
    if enable_splat:
        stages.append((task_splat.si(job_id), JobStage.SPLAT))
        
    stages.append((task_finalize.si(job_id), JobStage.EXPORT))
    
    # Filter out completed stages
    tasks_to_run = []
    for sig, stage_name in stages:
        if not is_stage_completed(job_id, stage_name):
            tasks_to_run.append(sig)
            
    if not tasks_to_run:
        logger.info(f"✅ All stages for job {job_id} already completed.")
        return job_id
        
    # Execute chain of remaining tasks
    pipeline_chain = chain(*tasks_to_run)
    pipeline_chain.apply_async(task_id=f"chain-{job_id}")

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_download", max_retries=3)
def task_download(self, job_id: str, image_urls: list = None):
    if is_stage_completed(job_id, JobStage.DOWNLOAD):
        logger.info(f"⏭️ Stage DOWNLOAD already completed for {job_id}")
        return job_id

    logger.info(f"📥 Starting DOWNLOAD for {job_id}")
    start_stage(job_id, JobStage.DOWNLOAD)
    
    try:
        storage = get_storage_provider()
        
        if image_urls:
            for idx, url in enumerate(image_urls):
                fname = f"img_{idx:03d}.jpg"
                remote_path = f"jobs/{job_id}/input/{fname}"
                
                # Fetch content
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                
                # Abstracted upload
                storage.upload_file(remote_path, resp.content)
            
        # Verify input exists
        files = storage.list_files(f"jobs/{job_id}/input/")
        if not files:
            raise RuntimeError("No input images found in storage.")
                
        complete_stage(job_id, JobStage.DOWNLOAD)
        return job_id
    except Exception as e:
        logger.error(f"❌ DOWNLOAD failed: {e}")
        fail_stage(job_id, JobStage.DOWNLOAD, str(e))
        self.retry(exc=e, countdown=settings.RETRY_BACKOFF_SECONDS)

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_preprocess", max_retries=3)
def task_preprocess(self, job_id: str):
    if is_stage_completed(job_id, JobStage.PREPROCESS):
        return job_id

    logger.info(f"🛠️ Starting PREPROCESS for {job_id}")
    start_stage(job_id, JobStage.PREPROCESS)
    
    try:
        import cv2
        import numpy as np
        storage = get_storage_provider()
        
        # 1. List input
        input_files = storage.list_files(f"jobs/{job_id}/input/")
        if not input_files:
            raise RuntimeError(f"No input images for job {job_id}")

        # 2. Process each image without local file leak (streaming/abstraction)
        for remote_input in input_files:
            if not remote_input.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
                
            # Download bytes
            img_bytes = storage.download_file(remote_input)
            
            # Decode with CV2
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                continue
            
            # Resize
            h, w = img.shape[:2]
            if max(h, w) > 2400:
                scale = 2400 / max(h, w)
                img = cv2.resize(img, (int(w*scale), int(h*scale)))
            
            # Encode and upload
            _, buffer = cv2.imencode(".jpg", img)
            storage.upload_file(f"jobs/{job_id}/input/preprocessed/{Path(remote_input).name}", buffer.tobytes())
                
        complete_stage(job_id, JobStage.PREPROCESS)
        return job_id
    except Exception as e:
        logger.error(f"❌ PREPROCESS failed: {e}")
        fail_stage(job_id, JobStage.PREPROCESS, str(e))
        self.retry(exc=e, countdown=settings.RETRY_BACKOFF_SECONDS)

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_sfm", queue="gpu_tasks")
def task_sfm(self, job_id: str):
    if is_stage_completed(job_id, JobStage.SFM):
        return job_id

    logger.info(f"🚀 Starting SFM (Modal) for {job_id}")
    start_stage(job_id, JobStage.SFM)
    
    try:
        import modal
        f = modal.Function.from_name(settings.MODAL_APP_NAME, "run_sfm")
        result = f.remote(job_id=job_id)
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.SFM)
            return job_id
        else:
            raise RuntimeError(result.get("error", MODAL_ERROR_MSG))
    except Exception as e:
        logger.error(f"❌ SFM failed: {e}")
        fail_stage(job_id, JobStage.SFM, str(e))
        raise

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_mvs", queue="gpu_tasks")
def task_mvs(self, job_id: str):
    if is_stage_completed(job_id, JobStage.MVS):
        return job_id

    logger.info(f"🚀 Starting MVS (Modal) for {job_id}")
    start_stage(job_id, JobStage.MVS)
    
    try:
        import modal
        f = modal.Function.from_name(settings.MODAL_APP_NAME, "run_mvs")
        result = f.remote(job_id=job_id)
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.MVS)
            return job_id
        else:
            raise RuntimeError(result.get("error", MODAL_ERROR_MSG))
    except Exception as e:
        logger.error(f"❌ MVS failed: {e}")
        fail_stage(job_id, JobStage.MVS, str(e))
        raise

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_mesh", queue="gpu_tasks")
def task_mesh(self, job_id: str):
    if is_stage_completed(job_id, JobStage.MESH):
        return job_id

    logger.info(f"🚀 Starting MESH (Modal) for {job_id}")
    start_stage(job_id, JobStage.MESH)
    
    try:
        import modal
        f = modal.Function.from_name(settings.MODAL_APP_NAME, "run_mesh")
        result = f.remote(job_id=job_id)
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.MESH)
            return job_id
        else:
            raise RuntimeError(result.get("error", MODAL_ERROR_MSG))
    except Exception as e:
        logger.error(f"❌ MESH failed: {e}")
        fail_stage(job_id, JobStage.MESH, str(e))
        raise

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_splat", queue="gpu_tasks")
def task_splat(self, job_id: str):
    if is_stage_completed(job_id, JobStage.SPLAT):
        return job_id

    logger.info(f"🚀 Starting SPLAT (Modal) for {job_id}")
    start_stage(job_id, JobStage.SPLAT)
    
    try:
        import modal
        f = modal.Function.from_name(settings.MODAL_APP_NAME, "run_splat")
        result = f.remote(job_id=job_id)
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.SPLAT)
            return job_id
        else:
            raise RuntimeError(result.get("error", MODAL_ERROR_MSG))
    except Exception as e:
        logger.error(f"❌ SPLAT failed: {e}")
        fail_stage(job_id, JobStage.SPLAT, str(e))
        raise

@celery_app.task(name="worker.pipeline.tasks.task_finalize")
def task_finalize(job_id: str):
    logger.info(f"✅ Finalizing job {job_id}")
    update_job_status(job_id, status=JobStatus.COMPLETED, current_stage=JobStage.EXPORT)
    return job_id
