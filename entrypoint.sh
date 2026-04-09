#!/bin/bash
set -e

# 🎓 TEACHER'S NOTE: This script starts either the API or the Worker.
# We check the 'ROLE' environment variable to decide what to run.

if [ "$ROLE" = "api" ]; then
    echo "🚀 Starting Morphic 3D API..."
    # Run database migrations if needed
    # alembic upgrade head
    exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
    
elif [ "$ROLE" = "worker" ]; then
    echo "⚙️ Starting Morphic 3D Celery Worker..."
    # Start Celery worker pointing to the app
    exec celery -A backend.core.celery_app worker --loglevel=info
    
else
    echo "❌ ERROR: No ROLE specified. Set ROLE=api or ROLE=worker."
    exit 1
fi
