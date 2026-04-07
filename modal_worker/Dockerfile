# Base Image with COLMAP pre-installed
FROM colmap/colmap:3.8

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Python, Opencv dependencies, and other utilities
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install required Python packages
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
    modal \
    pydantic \
    requests \
    opencv-python-headless \
    numpy \
    pillow

# Set the working directory
WORKDIR /app

# Ensure COLMAP is in PATH
ENV PATH="/usr/local/bin:${PATH}"

# Default command (can be overridden by Modal)
CMD ["python3"]
