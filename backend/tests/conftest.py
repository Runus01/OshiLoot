from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.merch.adapters import ebay


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        mal_client_id="test-mal-id",
        mal_client_secret="test-mal-secret",
        session_secret="test-session-secret",
        public_url="http://localhost:5173",
        link_signing_key="test-signing-key",
        storage="memory",
        ebay_client_id="",
        ebay_client_secret="",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    ebay._tokens.clear()
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client
