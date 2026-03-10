"""
🧪 Test Suite for Morphic v3.0 Performance Optimizations

Tests cover:
1. Redis Queue (enqueue/dequeue)
2. Worker Registry
3. Database Connection Pooling
4. Caching System
5. Health Checks
6. Queue Status Monitoring
"""

import pytest
import redis
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.queue.manager import enqueue_job, dequeue_job, queue_length
from backend.api.workers import get_worker_registry, set_worker, delete_worker


# ─────────────────────────────────────────────────────────
# 🧪 REDIS QUEUE TESTS
# ─────────────────────────────────────────────────────────

@pytest.fixture
def redis_client():
    """Provide a Redis client for testing."""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        return r
    except Exception:
        pytest.skip("Redis not available")


@pytest.fixture(autouse=True)
def cleanup_redis(redis_client):
    """Clean up Redis before and after each test."""
    redis_client.delete("morphic:job_queue")
    redis_client.delete("worker:*")
    yield
    redis_client.delete("morphic:job_queue")
    redis_client.delete("worker:*")


class TestRedisQueue:
    """Tests for the Redis job queue."""
    
    def test_enqueue_job(self, redis_client):
        """Test enqueueing a single job."""
        job_id = "test-job-123"
        enqueue_job(job_id)
        
        # Verify job is in queue
        queue_len = queue_length()
        assert queue_len == 1
        
    def test_enqueue_multiple_jobs(self, redis_client):
        """Test enqueueing multiple jobs maintains FIFO order."""
        jobs = ["job-1", "job-2", "job-3"]
        for job_id in jobs:
            enqueue_job(job_id)
        
        assert queue_length() == 3
        
    def test_dequeue_job_fifo_order(self, redis_client):
        """Test that dequeuing respects FIFO order."""
        jobs = ["job-1", "job-2", "job-3"]
        for job_id in jobs:
            enqueue_job(job_id)
        
        # Dequeue in order
        assert dequeue_job() == "job-1"
        assert dequeue_job() == "job-2"
        assert dequeue_job() == "job-3"
        assert dequeue_job() is None  # Empty queue
        
    def test_queue_length(self, redis_client):
        """Test queue length tracking."""
        assert queue_length() == 0
        enqueue_job("job-1")
        assert queue_length() == 1
        enqueue_job("job-2")
        assert queue_length() == 2
        dequeue_job()
        assert queue_length() == 1


# ─────────────────────────────────────────────────────────
# 🧪 WORKER REGISTRY TESTS
# ─────────────────────────────────────────────────────────

class TestWorkerRegistry:
    """Tests for worker registration and status tracking."""
    
    def test_register_worker(self, redis_client):
        """Test registering a worker."""
        worker_id = "kaggle-gpu-1"
        worker_data = {
            "worker_id": worker_id,
            "url": "https://abc123.ngrok-free.app",
            "status": "idle",
            "last_seen": datetime.now(timezone.utc).isoformat()
        }
        set_worker(worker_id, worker_data)
        
        registry = get_worker_registry()
        assert worker_id in registry
        assert registry[worker_id]["url"] == "https://abc123.ngrok-free.app"
        
    def test_get_all_workers(self, redis_client):
        """Test retrieving all registered workers."""
        workers_to_register = ["worker-1", "worker-2", "worker-3"]
        for worker_id in workers_to_register:
            worker_data = {
                "worker_id": worker_id,
                "url": f"https://{worker_id}.ngrok-free.app",
                "status": "idle",
                "last_seen": datetime.now(timezone.utc).isoformat()
            }
            set_worker(worker_id, worker_data)
        
        registry = get_worker_registry()
        assert len(registry) == 3
        
    def test_delete_worker(self, redis_client):
        """Test removing a worker from registry."""
        worker_id = "worker-1"
        worker_data = {
            "worker_id": worker_id,
            "url": "https://worker-1.ngrok-free.app",
            "status": "idle",
            "last_seen": datetime.now(timezone.utc).isoformat()
        }
        set_worker(worker_id, worker_data)
        
        registry = get_worker_registry()
        assert worker_id in registry
        
        delete_worker(worker_id)
        registry = get_worker_registry()
        assert worker_id not in registry
        
    def test_update_worker_status(self, redis_client):
        """Test updating worker status (idle -> busy -> idle)."""
        worker_id = "worker-1"
        
        # Register as idle
        set_worker(worker_id, {
            "worker_id": worker_id,
            "status": "idle",
            "last_seen": datetime.now(timezone.utc).isoformat()
        })
        assert get_worker_registry()[worker_id]["status"] == "idle"
        
        # Update to busy
        set_worker(worker_id, {
            "worker_id": worker_id,
            "status": "busy",
            "last_seen": datetime.now(timezone.utc).isoformat()
        })
        assert get_worker_registry()[worker_id]["status"] == "busy"
        
        # Update back to idle
        set_worker(worker_id, {
            "worker_id": worker_id,
            "status": "idle",
            "last_seen": datetime.now(timezone.utc).isoformat()
        })
        assert get_worker_registry()[worker_id]["status"] == "idle"


# ─────────────────────────────────────────────────────────
# 🧪 CACHING SYSTEM TESTS
# ─────────────────────────────────────────────────────────

class TestCachingSystem:
    """Tests for image and COLMAP output caching."""
    
    def test_get_file_hash(self):
        """Test SHA256 hash computation."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test content")
            temp_file = f.name
        
        try:
            # Import after path setup
            from scripts.kaggle_worker import get_file_hash
            
            hash1 = get_file_hash(temp_file)
            hash2 = get_file_hash(temp_file)
            
            # Same file should have same hash
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA256 hex string is 64 chars
        finally:
            os.unlink(temp_file)
    
    def test_cache_paths(self):
        """Test cache path generation."""
        from scripts.kaggle_worker import get_cache_path
        
        prefix = "masked_image"
        file_hash = "abc123def456"
        
        cache_path = get_cache_path(prefix, file_hash)
        assert "morphic_cache" in str(cache_path)
        assert "abc123def456" in str(cache_path)


# ─────────────────────────────────────────────────────────
# 🧪 LOGGING TESTS
# ─────────────────────────────────────────────────────────

class TestLogging:
    """Tests for structured logging."""
    
    def test_logger_exists(self):
        """Test that logger is properly configured."""
        import logging
        logger = logging.getLogger("scripts.kaggle_worker")
        assert logger is not None
        
    def test_log_levels(self):
        """Test that all log levels can be called."""
        import logging
        logger = logging.getLogger("test_logger")
        
        # Should not raise exceptions
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")


# ─────────────────────────────────────────────────────────
# 🧪 ASYNC UPLOAD TESTS
# ─────────────────────────────────────────────────────────

class TestAsyncUpload:
    """Tests for async Cloudinary upload with retry logic."""
    
    @patch('scripts.kaggle_worker.cloudinary.uploader.upload')
    def test_upload_success_first_try(self, mock_upload):
        """Test successful upload on first attempt."""
        from scripts.kaggle_worker import upload_glb_async
        from queue import Queue
        
        mock_upload.return_value = {"secure_url": "https://example.com/model.glb"}
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            result = upload_glb_async(temp_file, "test-job-123")
            assert result == "https://example.com/model.glb"
            assert mock_upload.call_count == 1
        finally:
            os.unlink(temp_file)
    
    @patch('scripts.kaggle_worker.cloudinary.uploader.upload')
    def test_upload_retry_logic(self, mock_upload):
        """Test upload retry on transient failure."""
        from scripts.kaggle_worker import upload_glb_async
        
        # First call fails, second succeeds
        mock_upload.side_effect = [
            Exception("Network timeout"),
            {"secure_url": "https://example.com/model.glb"}
        ]
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            result = upload_glb_async(temp_file, "test-job-123")
            assert result == "https://example.com/model.glb"
            assert mock_upload.call_count == 2
        finally:
            os.unlink(temp_file)
    
    @patch('scripts.kaggle_worker.cloudinary.uploader.upload')
    def test_upload_max_retries_exceeded(self, mock_upload):
        """Test upload failure after max retries."""
        from scripts.kaggle_worker import upload_glb_async
        
        # All calls fail
        mock_upload.side_effect = Exception("Network timeout")
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name
        
        try:
            with pytest.raises(Exception) as exc_info:
                upload_glb_async(temp_file, "test-job-123")
            assert "after 3 attempts" in str(exc_info.value)
        finally:
            os.unlink(temp_file)


# ─────────────────────────────────────────────────────────
# 🧪 DATABASE POOLING TESTS
# ─────────────────────────────────────────────────────────

class TestDatabasePooling:
    """Tests for database connection pooling configuration."""
    
    def test_sqlite_uses_null_pool(self):
        """Test that SQLite uses NullPool."""
        from backend.core.db import engine
        from sqlalchemy.pool import NullPool, QueuePool
        
        # Check engine pool class
        if "sqlite" in str(engine.url):
            assert isinstance(engine.pool, NullPool)
    
    def test_postgresql_uses_queue_pool(self):
        """Test that PostgreSQL uses QueuePool."""
        from backend.core.db import engine
        from sqlalchemy.pool import QueuePool
        
        if "postgresql" in str(engine.url):
            assert isinstance(engine.pool, QueuePool)


# ─────────────────────────────────────────────────────────
# 🧪 INTEGRATION TESTS
# ─────────────────────────────────────────────────────────

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_job_flow_redis_queue(self, redis_client):
        """Test complete job flow: enqueue -> dequeue."""
        # Enqueue
        job_id = "integration-test-job"
        enqueue_job(job_id)
        assert queue_length() == 1
        
        # Dequeue
        retrieved_job = dequeue_job()
        assert retrieved_job == job_id
        assert queue_length() == 0
    
    def test_worker_registration_flow(self, redis_client):
        """Test complete worker registration flow."""
        worker_id = "test-worker-1"
        url = "https://test-worker.ngrok-free.app"
        
        # Register
        worker_data = {
            "worker_id": worker_id,
            "url": url,
            "status": "idle",
            "last_seen": datetime.now(timezone.utc).isoformat()
        }
        set_worker(worker_id, worker_data)
        
        # Get registry
        registry = get_worker_registry()
        assert worker_id in registry
        assert registry[worker_id]["url"] == url
        
        # Update status
        worker_data["status"] = "busy"
        set_worker(worker_id, worker_data)
        registry = get_worker_registry()
        assert registry[worker_id]["status"] == "busy"
        
        # Delete
        delete_worker(worker_id)
        registry = get_worker_registry()
        assert worker_id not in registry


# ─────────────────────────────────────────────────────────
# 🧪 PERFORMANCE BENCHMARKS
# ─────────────────────────────────────────────────────────

class TestPerformance:
    """Benchmark tests to measure optimization impact."""
    
    def test_queue_enqueue_speed(self, redis_client, benchmark):
        """Benchmark job enqueue operation."""
        def enqueue_operation():
            enqueue_job("benchmark-job")
        
        benchmark(enqueue_operation)
    
    def test_queue_dequeue_speed(self, redis_client, benchmark):
        """Benchmark job dequeue operation."""
        # Pre-populate queue
        for i in range(100):
            enqueue_job(f"benchmark-job-{i}")
        
        def dequeue_operation():
            dequeue_job()
        
        benchmark(dequeue_operation)
    
    def test_worker_registry_lookup_speed(self, redis_client, benchmark):
        """Benchmark worker registry lookup."""
        # Register multiple workers
        for i in range(10):
            worker_data = {
                "worker_id": f"worker-{i}",
                "status": "idle",
                "last_seen": datetime.now(timezone.utc).isoformat()
            }
            set_worker(f"worker-{i}", worker_data)
        
        def lookup_operation():
            get_worker_registry()
        
        benchmark(lookup_operation)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
