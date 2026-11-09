FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY invoice_pipeline ./invoice_pipeline
RUN pip install --no-cache-dir ".[sheets]"
EXPOSE 8000
CMD ["uvicorn", "invoice_pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
