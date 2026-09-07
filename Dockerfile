# Production Dockerfile for AI Digital Marketing Command Center
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies and install.
# Core deps are required; google-ads (heavy: grpcio/protobuf) is best-effort so
# a memory-limited build never blocks the whole image. --prefer-binary forces
# prebuilt wheels instead of compiling grpcio from source.
COPY requirements.txt requirements-optional.txt ./
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt \
    && (pip install --no-cache-dir --prefer-binary -r requirements-optional.txt \
        || echo "WARN: optional deps (google-ads) not installed; app runs, live Google Ads reports library-missing until present")

# Copy application source code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs /app/logs/agents

# Expose server port
EXPOSE 8000

# Start command center
CMD ["python", "main.py"]
