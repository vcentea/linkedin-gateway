# LinkedIn Gateway Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements/base.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Create logs directory
RUN mkdir -p /app/logs

# Set default port (can be overridden via PORT env var)
ENV PORT=7778

# Expose port
EXPOSE ${PORT}

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start server (database schema is created by init-scripts/01-create-schema.sql)
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port ${PORT}"

