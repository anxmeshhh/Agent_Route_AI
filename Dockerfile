# ======================================================================
#  AgentRouteAI — Production Dockerfile
#  Multi-stage build: slim Python 3.12 image
# ======================================================================
FROM python:3.12-slim

# System deps for mysql-connector and cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run with gunicorn (gthread worker = SSE compatible)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--worker-class", "gthread", "--threads", "8", "--timeout", "120", "--keep-alive", "5", "wsgi:app"]
