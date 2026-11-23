FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements-serving.txt ./
RUN pip install --no-cache-dir -r requirements-serving.txt

COPY src/ ./src/
RUN mkdir -p /app/artifacts

USER 10001:10001
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn src.financial_exclusion.api.main:app --host 0.0.0.0 --port ${PORT:-10000} --no-access-log"]
