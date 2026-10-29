# Base images come from ECR Public rather than Docker Hub, which rate-limits anonymous pulls
# hard. ECR Public has limits too (1 pull/s and a shared data allowance when anonymous, 10/s
# once authenticated), so CI and the deploy workflow sign in first. Both images are
# overridable: a build with no AWS credentials can point PYTHON_IMAGE at another mirror.
ARG PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.12-slim
ARG ADAPTER_IMAGE=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0

FROM ${ADAPTER_IMAGE} AS adapter

FROM ${PYTHON_IMAGE}

# Does nothing outside Lambda. On Lambda it turns each invocation into an HTTP request to uvicorn.
COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter

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
