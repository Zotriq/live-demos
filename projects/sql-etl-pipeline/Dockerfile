FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY etl ./etl
RUN pip install --no-cache-dir .
COPY data ./data
ENTRYPOINT ["etl"]
CMD ["schedule", "--every", "60"]
