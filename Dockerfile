# --- Stage 1: Builder ---
FROM python:3.11-slim as builder

# Prevents Python from writing .pyc files and enables unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a wheels directory
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# --- Stage 2: Final Runtime ---
FROM python:3.11-slim

# Labels for metadata
LABEL maintainer="Bitcoin On-chain Team" \
      version="2.0" \
      description="Bitcoin Mempool Fee Prediction Framework"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Create a non-root user for security
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh appuser

# Install runtime dependencies ONLY (libgomp1 is needed for XGBoost/LightGBM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install libraries
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code with correct ownership
COPY --chown=appuser:appgroup . .

# Ensure data and models directories exist with correct permissions
RUN mkdir -p data models logs predictions && \
    chown -R appuser:appgroup data models logs predictions

# Switch to non-root user
USER appuser

# Expose API port
EXPOSE 1234

# Healthcheck for the API
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:1234/health || exit 1

# Default command (overridden in docker-compose)
CMD ["python", "scripts/live_predict.py", "--once"]
