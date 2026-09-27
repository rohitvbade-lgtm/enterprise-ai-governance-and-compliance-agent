# syntax=docker/dockerfile:1
FROM python:3.12-slim
# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app
# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*
# Install uv for high-speed package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
# Copy dependency definition
COPY pyproject.toml .
# Install dependencies using uv into system Python
RUN uv pip install --system --no-cache -e .
# Copy application directories and files
COPY backend/ backend/
COPY dashboard/ dashboard/
COPY knowledge/ knowledge/
COPY migrations/ migrations/
COPY scripts/ scripts/
COPY alembic.ini .
# Expose FastAPI backend (8000) and Streamlit dashboard (8501)
EXPOSE 8000 8501
# Default command: FastAPI backend server
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]