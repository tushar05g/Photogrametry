# 🎓 TEACHER'S NOTE: This Dockerfile sets up your 3D scanning environment.
# We use python:3.10-slim for a small, fast base image.
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/code

# Install system dependencies for COLMAP and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    colmap \
    xvfb \
    libgl1 \
    libglvnd0 \
    libglx0 \
    libglew2.2 \
    libglib2.0-0 \
    git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /code

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create output and logs directories
RUN mkdir -p output logs && chmod 777 output logs

# Set up entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
