#!/bin/bash
# Comprehensive test runner for 3D Scanner project

set -e

echo "🧪 Running 3D Scanner Tests..."

# Install dependencies if not already
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv
fi

source .venv/bin/activate
pip install -e .

# Run tests
echo "🧪 Running unit tests..."
pytest tests/ -v

# Run integration tests if database is available
if [ -n "$DATABASE_URL" ]; then
    echo "🔗 Running integration tests..."
    pytest tests/ -k "integration" -v
else
    echo "⚠️ Skipping integration tests (DATABASE_URL not set)"
fi

# Check code quality
echo "🔍 Checking code quality..."
python -m flake8 backend/ scripts/ --max-line-length=120 --ignore=E203,W503

echo "✅ All tests passed!"