# Production Dockerfile for SkyCap AI
FROM python:3.9-slim

# Build-time metadata (optional)
ARG COMMIT_SHA="unknown"
ARG BUILD_TIMESTAMP
ARG APP_VERSION

LABEL org.opencontainers.image.source="skycap-ai" \
    org.opencontainers.image.revision="$COMMIT_SHA" \
    org.opencontainers.image.created="$BUILD_TIMESTAMP" \
    org.opencontainers.image.version="$APP_VERSION"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY intelligent_agent.py .
COPY master_knowledge_base.json .

# Set environment variables (include version if passed)
ENV PYTHONUNBUFFERED=1 \
    SKYCAP_KB_PATH=master_knowledge_base.json \
    PORT=8080 \
    COMMIT_SHA=${COMMIT_SHA} \
    APP_VERSION=${APP_VERSION}

# Expose port
EXPOSE 8080

# Use gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app