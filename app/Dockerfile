# syntax=docker/dockerfile:1
# The Sorcerer's Stone — FastAPI Application Image
# Ref: .kiro/specs/phase-1-architecture/design.md §2.2 (container hardening)
#
# Security:
#   - Non-root user (UID 1000)
#   - read-only rootfs (enforced at container runtime, not in Dockerfile)
#   - Pinned base image
#   - No dev dependencies in production image
#   - Multi-stage build for minimal attack surface

FROM python:3.12-slim AS base

# System deps needed at runtime (asyncpg needs libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 app && \
    useradd -u 1000 -g app -m -s /bin/bash app

WORKDIR /app

# ── Builder stage: install Python deps ────────────────────────────────────────
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Production image ──────────────────────────────────────────────────────────
FROM base AS production

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ /app/app/

# Switch to non-root user
USER 1000:1000

# Expose FastAPI port (internal network only — Caddy proxies)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

# Run with uvicorn
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
