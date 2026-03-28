# ============================================================
# PULSE — Newsroom AI Orchestrator
# Docker image (linux/amd64)
# ============================================================
FROM --platform=linux/amd64 python:3.10-slim-bullseye

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by azure-cognitiveservices-speech
# Bullseye ships OpenSSL 1.1 which the Speech SDK requires
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libssl-dev \
        ca-certificates \
        libasound2 \
        libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, static assets, and environment config
COPY app/ app/
COPY static/ static/
COPY scripts/ scripts/
COPY .env .

# Expose the default FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
