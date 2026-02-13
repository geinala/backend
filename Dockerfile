# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Install uv
RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./

# Build virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv sync --no-dev


# Production image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY app/ app/
COPY .env.example .env

# Health check (can connect to Redis)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from app.core import get_redis_connection; get_redis_connection().ping()" || exit 1

# Default: run worker
CMD ["rq", "worker"]
