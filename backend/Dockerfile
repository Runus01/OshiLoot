# The Python base comes from Google's mirror of Docker Hub, which needs no sign-in. The Lambda
# Web Adapter is only published on ECR Public, where anonymous pulls are capped at 1/s with a
# shared data allowance that busy CI runners use up ("429 ... Data limit exceeded"). So only
# the deploy workflow pulls the adapter, after signing in to ECR Public.
ARG PYTHON_IMAGE=mirror.gcr.io/library/python:3.12-slim
ARG ADAPTER_IMAGE=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0

FROM ${ADAPTER_IMAGE} AS adapter

# The app on its own. CI and docker compose build only this stage (--target app), so they
# never reach ECR Public. BuildKit skips stages the target doesn't depend on.
FROM ${PYTHON_IMAGE} AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

EXPOSE 8080
# --no-access-log: uvicorn's access log prints full paths, which include MAL usernames.
# The app logs route templates instead (app/core/logging.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

# What Lambda runs, and the default target: the app plus the Lambda Web Adapter extension,
# which turns each invocation into an HTTP request to uvicorn.
FROM app AS lambda

COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/api/healthz
