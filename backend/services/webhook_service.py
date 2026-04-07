import logging
import httpx
import time
from typing import Dict, Optional
from backend.config import settings

logger = logging.getLogger(__name__)

async def trigger_webhook(job_id: str, status: str, metadata: Optional[Dict] = None, webhook_url: Optional[str] = None):
    if not webhook_url:
        logger.info(f"No webhook URL provided for job {job_id}")
        return

    payload = {
        "job_id": job_id,
        "status": status,
        "metadata": metadata or {},
        "timestamp": time.time()
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                logger.info(f"Webhook sent successfully for job {job_id} (attempt {attempt+1})")
                return
        except Exception as e:
            logger.warning(f"Failed to send webhook for job {job_id} (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) # Exponential backoff
            else:
                logger.error(f"Failed to send webhook after {max_retries} attempts")
