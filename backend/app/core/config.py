from functools import lru_cache
from typing import Literal

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SIGNING_KEY = "dev-only-not-a-secret"


class Settings(BaseSettings):
    """Read from environment variables (case-insensitive) or a local .env file.

    On Lambda, SSM_PREFIX is set and secrets are loaded from SSM Parameter Store,
    e.g. /oshiloot/mal_client_id overrides MAL_CLIENT_ID.
    """

    # The repo-root .env works whether you start uvicorn from the repo root or from backend/.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    mal_client_id: str = ""

    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_campaign_id: str = ""
    ebay_env: Literal["production", "sandbox"] = "production"

    # Paste the link from CDJapan's "Create Link to Arbitrary Page" menu here and put
    # {path} where the destination path goes. Empty means plain (non-affiliate) links.
    cdjapan_affiliate_template: str = ""

    link_signing_key: str = DEV_SIGNING_KEY

    storage: Literal["memory", "dynamodb"] = "memory"
    dynamodb_endpoint: str | None = None
    cache_table: str = "oshiloot-cache"
    clicks_table: str = "oshiloot-clicks"
    aws_region: str = "us-west-2"
    ssm_prefix: str | None = None

    http_timeout_seconds: float = 8.0
    store_deadline_seconds: float = 3.0


def _load_ssm(prefix: str, region: str) -> dict[str, str]:
    client = boto3.client("ssm", region_name=region)
    values: dict[str, str] = {}
    paginator = client.get_paginator("get_parameters_by_path")
    for page in paginator.paginate(Path=prefix, WithDecryption=True):
        for param in page["Parameters"]:
            values[param["Name"].removeprefix(prefix).lower()] = param["Value"]
    return values


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.ssm_prefix:
        overrides = _load_ssm(settings.ssm_prefix, settings.aws_region)
        known = {k: v for k, v in overrides.items() if k in Settings.model_fields}
        settings = settings.model_copy(update=known)
        if settings.link_signing_key == DEV_SIGNING_KEY:
            raise RuntimeError(
                f"Set {settings.ssm_prefix}link_signing_key in SSM before deploying."
            )
    return settings
