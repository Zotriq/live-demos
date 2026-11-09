FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY wa_agent ./wa_agent
RUN pip install --no-cache-dir .
ENV DATABASE_PATH=/data/whatsapp_agent.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "wa_agent.app:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
