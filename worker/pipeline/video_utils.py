import cv2
import logging
import os
import tempfile
from pathlib import Path
from typing import List
from storage.provider import StorageProvider
from backend.config import settings

logger = logging.getLogger(__name__)

MIN_VIDEO_DURATION_SECONDS = 1.0
MAX_VIDEO_DURATION_SECONDS = 180.0

def validate_video_file(video_path: Path, job_id: str = "unknown") -> None:
    """
    Basic validation to fail early on unsupported/corrupt videos.
    """
    if not video_path.exists() or video_path.stat().st_size == 0:
        raise RuntimeError(f"Job {job_id}: Video file is missing or empty: {video_path.name}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Job {job_id}: Unable to open video file: {video_path.name}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        if fps <= 0:
            fps = 30.0

        duration = frame_count / fps if frame_count > 0 else 0.0
        if duration < MIN_VIDEO_DURATION_SECONDS:
            raise RuntimeError(
                f"Job {job_id}: Video is too short ({duration:.2f}s). "
                f"Minimum supported duration is {MIN_VIDEO_DURATION_SECONDS:.1f}s."
            )
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise RuntimeError(
                f"Job {job_id}: Video is too long ({duration:.2f}s). "
                f"Maximum supported duration is {MAX_VIDEO_DURATION_SECONDS:.0f}s."
            )

        ok, _ = cap.read()
        if not ok:
            raise RuntimeError(f"Job {job_id}: Video appears corrupted (cannot decode frames): {video_path.name}")
    finally:
        cap.release()

def extract_frames_from_video(
    video_path: Path, 
    output_dir: Path, 
    fps: float = 2.0,
    job_id: str = "unknown"
) -> List[Path]:
    """
    Extracts frames from a local video file at a specified FPS.
    Returns a list of local paths to the extracted frames.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0 # Fallback
        
    interval = int(video_fps / fps)
    if interval < 1:
        interval = 1

    frame_count = 0
    extracted_paths = []
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % interval == 0:
            frame_name = f"frame_{video_path.stem}_{frame_count:06d}.jpg"
            frame_path = output_dir / frame_name
            
            # Save frame
            cv2.imwrite(str(frame_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            extracted_paths.append(frame_path)
            
        frame_count += 1
        
    cap.release()
    logger.info(f"Job {job_id}: Extracted {len(extracted_paths)} frames from {video_path.name}")
    return extracted_paths

def process_job_videos(job_id: str, storage: StorageProvider):
    """
    Downloads all videos for a job, extracts frames, and uploads them to the input folder.
    """
    video_files = storage.list_files(f"jobs/{job_id}/videos/")
    if not video_files:
        logger.warning(f"No videos found for job {job_id}")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        video_dir = tmp_path / "videos"
        frames_dir = tmp_path / "frames"
        video_dir.mkdir()
        frames_dir.mkdir()

        for remote_video in video_files:
            # Download video
            local_video = video_dir / Path(remote_video).name
            storage.download_file(remote_video, local_video)

            # Validate before extraction to fail fast with a user-friendly error.
            validate_video_file(local_video, job_id=job_id)
            
            # Extract frames
            extract_frames_from_video(
                local_video, 
                frames_dir, 
                fps=settings.FRAME_EXTRACTION_FPS,
                job_id=job_id
            )

        # Upload all frames to input/
        extracted_frames = list(frames_dir.glob("*.jpg"))
        for frame_path in extracted_frames:
            remote_path = f"jobs/{job_id}/input/{frame_path.name}"
            storage.upload_file(remote_path, frame_path)
            
        logger.info(f"Job {job_id}: Uploaded {len(extracted_frames)} frames to storage")
