import logging
import json
import time
import functools
from enum import Enum
from typing import Any, Callable, Optional
from datetime import datetime

# 🔍 Failure Classification for Production RCA
class FailureCategory(str, Enum):
    DATA_ERROR = "DATA_ERROR"         # Invalid images, blurry, too few
    COMPUTE_ERROR = "COMPUTE_ERROR"   # COLMAP crash, GPU driver, CUDA OOM
    TIMEOUT = "TIMEOUT"               # GPU wall-time limit exceeded
    STORAGE_ERROR = "STORAGE_ERROR"   # NFS full, I/O connection loss
    MEMORY_ERROR = "MEMORY_ERROR"     # Container RAM exhaustion

class JSONFormatter(logging.Formatter):
    """
    Structured JSON Formatter for production observability (Datadog/NewRelic/ELK).
    Supports Distributed Tracing IDs.
    """
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "span_id": getattr(record, "otelSpanID", None),
            "trace_id": getattr(record, "otelTraceID", None),
        }
        if hasattr(record, "job_id"):
            log_entry["job_id"] = record.job_id
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    for h in logger.handlers[:-1]:
        logger.removeHandler(h)

def classify_failure(error_msg: str) -> FailureCategory:
    """Classifies raw error messages into actionable categories."""
    msg = error_msg.upper()
    if "RESOURCE_LIMIT_EXCEEDED: GPU TIME" in msg: return FailureCategory.TIMEOUT
    if "RESOURCE_LIMIT_EXCEEDED: DISK" in msg: return FailureCategory.STORAGE_ERROR
    if "MEMORY_LIMIT_EXCEEDED" in msg: return FailureCategory.MEMORY_ERROR
    if "INSUFFICIENT IMAGES" in msg: return FailureCategory.DATA_ERROR
    return FailureCategory.COMPUTE_ERROR

def trace_stage_performance(stage_name: str):
    """Decorator to log stage-level telemetry for distributed tracing."""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logging.info(f"START_STAGE: {stage_name}")
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logging.info(f"END_STAGE: {stage_name} | DURATION: {duration:.2f}s | STATUS: SUCCESS")
                return result
            except Exception as e:
                duration = time.time() - start_time
                category = classify_failure(str(e))
                logging.error(f"END_STAGE: {stage_name} | DURATION: {duration:.2f}s | STATUS: FAILED | CATEGORY: {category}")
                raise e
        return wrapper
    return decorator
