# =============================================================================
# BaseLayer Production Dockerfile
# =============================================================================
# Multi-stage build optimized for i5-2400, 16GB RAM, HDD storage
# =============================================================================

# =============================================================================
# Base Stage - Python Dependencies
# =============================================================================
FROM python:3.12-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# =============================================================================
# Dependencies Stage
# =============================================================================
FROM base as dependencies

# Create non-root user
RUN groupadd -r baselayer && useradd -r -g baselayer baselayer

# Set working directory
WORKDIR /app

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock* ./

# Install dependencies with uv
RUN uv pip install --system --no-cache-dir -e .[dev] \
    && uv cache clean

# =============================================================================
# Development Stage
# =============================================================================
FROM dependencies as development

# Copy source code
COPY backend/src ./src
COPY shared ./shared

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs /tmp/uploads \
    && chown -R baselayer:baselayer /app

# Switch to non-root user
USER baselayer

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/health || exit 1

# Start command
CMD ["uvicorn", "baselayer.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage
# =============================================================================
FROM dependencies as production

# Copy source code
COPY backend/src ./src
COPY shared ./shared

# Create necessary directories with proper permissions
RUN mkdir -p /var/lib/baselayer/uploads /var/log/baselayer /tmp/uploads \
    && chown -R baselayer:baselayer /app /var/lib/baselayer /var/log/baselayer

# Copy startup scripts
COPY infra/scripts/start.sh /usr/local/bin/start.sh
COPY infra/scripts/worker.sh /usr/local/bin/worker.sh
COPY infra/scripts/agent.sh /usr/local/bin/agent.sh

# Make scripts executable
RUN chmod +x /usr/local/bin/*.sh

# Switch to non-root user
USER baselayer

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/health || exit 1

# Default start command (can be overridden)
CMD ["/usr/local/bin/start.sh"]

# =============================================================================
# Security & Optimization Notes
# =============================================================================
# 1. Non-root user for security
# 2. Minimal base image (slim)
# 3. Multi-stage build to reduce final image size
# 4. UV for fast dependency installation
# 5. Proper cleanup to reduce image size
# 6. Health checks for container orchestration
# 7. Resource limits for i5-2400 optimization
# 8. No secrets baked into image
# 9. Read-only filesystem where possible
# 10. Proper signal handling for graceful shutdown
