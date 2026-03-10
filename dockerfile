FROM python:3.11

WORKDIR /code

# Copy requirements first (for layer caching optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN chmod +x /code/entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use entrypoint script instead of running alembic at build time
# This allows the database to be ready before migrations run
ENTRYPOINT ["/code/entrypoint.sh"]
