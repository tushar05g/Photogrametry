import os
import logging
import requests
import json
import time
from pathlib import Path
from celery import chain
from celery.exceptions import Ignore
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
from backend.core.db import SessionLocal
from backend.models.models import Job
from backend.config import settings

logger = logging.getLogger(__name__)

MODAL_ERROR_MSG = "Unknown error on Modal"
DEBUG_LOG_PATH = "/home/harpreet/Documents/3d_scanner/.cursor/debug-c66765.log"
DEBUG_SESSION_ID = "c66765"


def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict):
    payload = {
        "sessionId": DEBUG_SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, default=str) + "\n")

# 🏁 v9.0.0: Fully Abstracted & Resumable Pipeline

@celery_app.task(name="worker.pipeline.tasks.initiate_pipeline")
def initiate_pipeline(job_id: str, image_urls: list = None, enable_dense: bool = True, enable_splat: bool = True):
    """
    Orchestrates the granular tasks. If job already exists, picks up from where it left off.
    """
    logger.info(f"🚀 (Re)Initiating pipeline for job {job_id}")
    
    # 1. Start Job in DB
    update_job_status(job_id, status=JobStatus.IN_PROGRESS)
    
    # Check if video job
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        is_video = job.is_video if job else False

    # Define generic stage sequence
    # First task gets initial arguments, subsequent tasks receive job_id from chain
    stages = []
    
    if is_video:
        stages.append((task_extract_frames.s(job_id), JobStage.FRAME_EXTRACTION))
    else:
        logger.info(f"Skipping frame extraction for non-video job {job_id}")
    stages.append((task_download.si(job_id, image_urls), JobStage.DOWNLOAD))

    stages.extend([
        (task_preprocess.si(job_id), JobStage.PREPROCESS),
        (task_sfm.si(job_id), JobStage.SFM)
    ])
    
    if enable_dense:
        stages.append((task_mvs.si(job_id), JobStage.MVS))
        stages.append((task_mesh.si(job_id), JobStage.MESH))
        
    if enable_splat:
        stages.append((task_splat.si(job_id), JobStage.SPLAT))
        
    stages.append((task_finalize.si(job_id), JobStage.EXPORT))
    
    # Don't filter completed stages - keep chain intact
    # Each task checks completion at runtime and skips if already done
    tasks_to_run = [sig for sig, stage_name in stages]
    # region agent log
    _debug_log(
        run_id="model-quality-check",
        hypothesis_id="H1",
        location="worker/pipeline/tasks.py:initiate_pipeline",
        message="Pipeline task chain selected",
        data={
            "job_id": job_id,
            "is_video": is_video,
            "enable_dense": enable_dense,
            "enable_splat": enable_splat,
            "tasks_to_run_count": len(tasks_to_run),
            "tasks_to_run": [str(t) for t in tasks_to_run],
        },
    )
    # endregion
            
    if not tasks_to_run:
        logger.info(f"✅ All stages for job {job_id} already completed.")
        return job_id
        
    # Execute chain of remaining tasks
    pipeline_chain = chain(*tasks_to_run)
    # Ensure cleanup and webhook run on completion
    cleanup_sig = task_cleanup_assets.si(job_id)
    webhook_sig = task_send_webhook.si(job_id)
    
    pipeline_chain.apply_async(
        task_id=f"chain-{job_id}",
        link=[webhook_sig, cleanup_sig],
        link_error=[webhook_sig, cleanup_sig]
    )

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_download", max_retries=3)
def task_download(self, job_id: str, image_urls: list = None, *args, **kwargs):
    if is_stage_completed(job_id, JobStage.DOWNLOAD):
        logger.info(f"⏭️ Stage DOWNLOAD already completed for {job_id}")
        return job_id

    logger.info(f"📥 Starting DOWNLOAD for {job_id}")
    start_stage(job_id, JobStage.DOWNLOAD)
    
    try:
        storage = get_storage_provider()

        # For direct uploads (image/video), files are already persisted in storage.
        # Avoid extra listing latency/rate-limit pressure and mark this stage complete.
        if not image_urls:
            logger.info(f"No image URLs provided; using pre-uploaded assets for job {job_id}")
            complete_stage(job_id, JobStage.DOWNLOAD)
            return job_id

        existing_input_files = storage.list_files(f"jobs/{job_id}/input/")
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

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_extract_frames", max_retries=2)
def task_extract_frames(self, job_id: str):
    if is_stage_completed(job_id, JobStage.FRAME_EXTRACTION):
        return job_id

    logger.info(f"🎞️ Starting FRAME_EXTRACTION for {job_id}")
    start_stage(job_id, JobStage.FRAME_EXTRACTION)
    
    try:
        from worker.pipeline.video_utils import process_job_videos
        storage = get_storage_provider()
        
        process_job_videos(job_id, storage)
        
        complete_stage(job_id, JobStage.FRAME_EXTRACTION)
        return job_id
    except Exception as e:
        logger.error(f"❌ FRAME_EXTRACTION failed: {e}")
        fail_stage(job_id, JobStage.FRAME_EXTRACTION, str(e))
        raise

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
        processed_count = 0
        decode_failures = 0
        resized_count = 0

        # 2. Process each image without local file leak (streaming/abstraction)
        for remote_input in input_files:
            if not remote_input.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            normalized_input = remote_input.lstrip("/")
                
            # Download bytes
            img_bytes = storage.download_file(normalized_input)
            
            # Decode with CV2
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                decode_failures += 1
                continue
            
            # 🏁 v10.0.0: High-Resolution Preprocessing
            h, w = img.shape[:2]
            target_dim = 1024
            if max(h, w) > 2400:
                scale = 2400 / max(h, w)
                img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
                resized_count += 1
            elif max(h, w) < target_dim:
                logger.info(f"🔍 Upscaling small image {normalized_input} ({w}x{h} -> {target_dim})")
                scale = target_dim / max(h, w)
                img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_CUBIC)
                resized_count += 1
            
            # Encode and upload.
            # Keep lossless PNG to preserve corners/textures used by SfM matching.
            ok, buffer = cv2.imencode(".png", img)
            if not ok:
                decode_failures += 1
                continue
            storage.upload_file(
                f"jobs/{job_id}/input/preprocessed/{Path(normalized_input).stem}.png",
                buffer.tobytes()
            )
            processed_count += 1
        # region agent log
        _debug_log(
            run_id="model-quality-check",
            hypothesis_id="H2",
            location="worker/pipeline/tasks.py:task_preprocess",
            message="Preprocess output summary",
            data={
                "job_id": job_id,
                "input_count": len(input_files),
                "processed_count": processed_count,
                "decode_failures": decode_failures,
                "resized_count": resized_count,
            },
        )
        # endregion
                
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
        if settings.WORKER_STRATEGY == "pull":
            logger.info(f"⏳ WORKER_STRATEGY is 'pull'. Job {job_id} is waiting for a remote worker to poll it.")
            # We keep it as PENDING and don't start anything. 
            # The worker_api.poll() will pick it up and mark it IN_PROGRESS.
            from backend.core.db import SessionLocal
            from backend.models.models import Stage
            with SessionLocal() as db:
                stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == JobStage.SFM).first()
                if stage:
                    stage.status = StageStatus.PENDING # Ensure it's pollable
                    db.commit()
            
            # 🏁 v11.0.0: Halt the chain. 
            # The remote worker will resume by calling /complete which starts the next task.
            raise Ignore()

        import modal
        f = modal.Function.from_name("photogrammetry-worker", "run_sfm")
        # v10.0.0: Capture quality metrics
        metadata = f.remote(job_id)
        logger.info(f"📊 SFM Metadata: {metadata}")
        
        # Results are nested under "results" from run_stage
        res_data = metadata.get("results", {})
        num_reg = res_data.get("num_registered", 0)
        total = res_data.get("total_images", 1)
        sparse_exists = res_data.get("sparse_model_exists", False)
        
        # Update Quality Report
        update_quality_report(job_id, {"sfm": metadata})
        
        # Quality Gate
        if not sparse_exists or (total > 3 and (num_reg / total) < 0.5):
             msg = f"Alignment Failed: registered {num_reg}/{total} images. Dataset lacks sufficient visual overlap."
             update_recommendation(job_id, msg)
             raise RuntimeError(msg)
        
        complete_stage(job_id, JobStage.SFM)
        return job_id
    except Exception as e:
        if isinstance(e, Ignore):
            raise
        error_msg = str(e).lower()
        if "spend limit reached" in error_msg or "resourceexhausted" in error_msg:
            logger.warning(f"⚠️ Modal spend limit reached for {job_id}. Falling back to Kaggle remote worker.")
            from backend.core.db import SessionLocal
            from backend.models.models import Stage
            with SessionLocal() as db:
                stage = db.query(Stage).filter(Stage.job_id == job_id, Stage.stage_name == JobStage.SFM).first()
                if stage:
                    stage.status = StageStatus.PENDING # Make pollable again
                    db.commit()
            raise Ignore()

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
        f = modal.Function.from_name("photogrammetry-worker", "run_mvs")
        result = f.remote(job_id)
        
        logger.info(f"📊 MVS Metadata: {result}")
        
        # Update Quality Report
        update_quality_report(job_id, {"mvs": result})
        
        if result.get("status") == "failed":
            raise RuntimeError(result.get("error", "MVS stage failed on Modal"))

        # Quality Check
        inner_results = result.get("results", {})
        point_count = inner_results.get("point_count", 0)
        if point_count < 500:
             msg = f"Low point cloud density ({point_count} points). Output may be sparse."
             update_recommendation(job_id, "Subject surface has no detectable texture. Try adding some patterns or improved lighting.")
             # 🏁 v10.1.0: Soft-fail for MVS
             inner_results["warning"] = msg
             complete_stage(job_id, JobStage.MVS, results=inner_results)
             return job_id
             
        complete_stage(job_id, JobStage.MVS, results=inner_results)
        return job_id
    except Exception as e:
        logger.warning(f"⚠️ MVS failed but continuing pipeline for {job_id}: {e}")
        complete_stage(
            job_id, 
            JobStage.MVS, 
            results={
                "error": str(e),
                "status": "failed_continued"
            }
        )
        return job_id

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_mesh", queue="gpu_tasks")
def task_mesh(self, job_id: str):
    if is_stage_completed(job_id, JobStage.MESH):
        return job_id

    logger.info(f"🚀 Starting MESH (Modal) for {job_id}")
    start_stage(job_id, JobStage.MESH)
    
    try:
        import modal
        f = modal.Function.from_name("photogrammetry-worker", "run_mesh")
        result = f.remote(job_id=job_id)
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.MESH, results=result.get("results"))
            return job_id
        else:
            raise RuntimeError(result.get("error", MODAL_ERROR_MSG))
    except Exception as e:
        # 🏁 v10.1.0: Soft-fail mesh so the pipeline can continue to SPLAT/EXPORT.
        logger.warning(f"⚠️ MESH failed but continuing pipeline for {job_id}: {e}")
        complete_stage(
            job_id,
            JobStage.MESH,
            results={
                "warning": str(e),
                "status": "failed_continued"
            }
        )
        return job_id

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
        # region agent log
        _debug_log(
            run_id="model-quality-check",
            hypothesis_id="H5",
            location="worker/pipeline/tasks.py:task_splat",
            message="Modal SPLAT result",
            data={"job_id": job_id, "result": result},
        )
        # endregion
        
        if result.get("status") == "completed":
            complete_stage(job_id, JobStage.SPLAT, results=result.get("results"))
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

@celery_app.task(bind=True, name="worker.pipeline.tasks.task_send_webhook", max_retries=5)
def task_send_webhook(self, job_id: str):
    """
    Sends a POST notification to the registered webhook_url with job results.
    """
    logger.info(f"📡 Checking for webhook for job {job_id}")
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job or not job.webhook_url:
            logger.info(f"⏭️ No webhook_url for job {job_id}")
            return job_id

        webhook_url = job.webhook_url
        payload = {
            "job_id": job.job_id,
            "project_name": job.project_name,
            "status": job.status.value,
            "current_stage": job.current_stage.value,
            "results": job.results,
            "quality_report": job.quality_report,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None
        }

    try:
        logger.info(f"📤 Sending webhook to {webhook_url}")
        response = requests.post(webhook_url, json=payload, timeout=10)
        
        # 🏁 v10.2.0: Handle unrecoverable 404s
        if response.status_code == 404:
            logger.warning(f"🚫 Webhook 404 (Not Found) for job {job_id}. Skipping retries.")
            with SessionLocal() as db:
                job = db.query(Job).filter(Job.job_id == job_id).first()
                if job:
                    job.webhook_status = "failed"
                    db.commit()
            return job_id
            
        response.raise_for_status()
        
        with SessionLocal() as db:
            job = db.query(Job).filter(Job.job_id == job_id).first()
            if job:
                job.webhook_status = "sent"
                db.commit()
        logger.info(f"✅ Webhook sent successfully for job {job_id}")
        
    except requests.exceptions.HTTPError as h_err:
        status_code = getattr(h_err.response, "status_code", None)
        if status_code and (status_code >= 500 or status_code == 429):
            logger.warning(f"⚠️ Webhook server error ({status_code}); retrying...")
            self.retry(exc=h_err, countdown=settings.RETRY_BACKOFF_SECONDS)
        else:
            logger.error(f"❌ Permanent webhook failure ({status_code}) for {job_id}")
            with SessionLocal() as db:
                job = db.query(Job).filter(Job.job_id == job_id).first()
                if job:
                    job.webhook_status = "failed"
                    db.commit()
    except Exception as e:
        logger.warning(f"⚠️ Webhook transient error for {job_id}: {e}; retrying...")
        self.retry(exc=e, countdown=settings.RETRY_BACKOFF_SECONDS)
        
    return job_id

@celery_app.task(name="worker.pipeline.tasks.task_cleanup_assets")
def task_cleanup_assets(job_id: str):
    logger.info(f"🧹 Starting CLEANUP for {job_id}")
    try:
        import modal
        f = modal.Function.from_name("photogrammetry-worker", "cleanup_job")
        f.remote(job_id)
        logger.info(f"✅ CLEANUP successful for job {job_id}")
    except Exception as e:
        logger.warning(f"Cleanup encountered an issue for job {job_id}, but continuing: {e}")
    return job_id

def update_recommendation(job_id: str, message: str):
    """
    Helper to append/update recommendation in Job.results JSON
    """
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            results = job.results or {}
            # We preserve existing results but overwrite the recommendation
            results["recommendation"] = message
            job.results = results
            db.commit()
            logger.info(f"📝 Added recommendation to job {job_id}: {message}")

def update_quality_report(job_id: str, data: dict):
    """
    Helper to merge data into Job.quality_report JSON column
    """
    with SessionLocal() as db:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if job:
            report = job.quality_report or {}
            report.update(data)
            job.quality_report = report
            db.commit()
            logger.info(f"📊 Updated quality report for job {job_id}")
