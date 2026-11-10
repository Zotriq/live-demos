FROM python:3.12-slim AS base

WORKDIR /app

# System dependencies for psycopg (binary build already avoids needing libpq-dev,
# but curl is kept for the container health check).
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY prompts/ ./prompts/

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Runs as a non-root user for defense-in-depth.
RUN useradd --create-home appuser
USER appuser

CMD ["uvicorn", "pdf_rag.main:app", "--host", "0.0.0.0", "--port", "8000"]
