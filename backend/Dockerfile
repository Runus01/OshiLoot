FROM public.ecr.aws/docker/library/python:3.12-slim

# Does nothing outside Lambda. On Lambda it turns each invocation into an HTTP request to uvicorn.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter

ENV AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/api/healthz \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8080
# --no-access-log: uvicorn's access log prints full paths, which include MAL usernames.
# The app logs route templates instead (app/core/logging.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
