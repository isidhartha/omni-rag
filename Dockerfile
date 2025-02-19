# ---------------------------------------------------------------------------
# OmniRAG Backend — Multi-stage Docker build
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

LABEL maintainer="OmniRAG Team"
LABEL description="OmniRAG Multimodal RAG Knowledge Engine"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ffmpeg \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Builder stage — install Python deps
# ---------------------------------------------------------------------------
FROM base AS builder

COPY backend/requirements.txt /app/requirements.txt

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM base AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ /app/backend/
COPY .env.example /app/.env.example

# Create non-root user
RUN useradd --create-home --shell /bin/bash omnirag && \
    mkdir -p /tmp/omnirag/uploads /tmp/omnirag/index && \
    chown -R omnirag:omnirag /app /tmp/omnirag

USER omnirag

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
