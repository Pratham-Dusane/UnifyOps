# UnifyOps Backend - Dockerfile
# Production deployment to GCP Cloud Run

FROM python:3.12-slim AS base

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose default port
EXPOSE 8000

# Run with uvicorn listening on GCP Cloud Run dynamic PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
