#!/bin/bash
set -e

echo "🚀 Running database migrations..."
# Wait for postgres if needed (but we are using Neon/remote DB so not needed)
alembic upgrade head
echo "✅ Migrations complete"

echo "🌍 Starting FastAPI server..."
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
