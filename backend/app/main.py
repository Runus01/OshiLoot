"""One FastAPI app, five modules. Each module owns its routes and may only import app.core."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import anime, go, merch, music, regions
from app.core.config import Settings, get_settings
from app.core.logging import RequestLogMiddleware, configure_logging
from app.core.storage import build_storage


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved = settings or get_settings()
        app.state.settings = resolved
        app.state.http = httpx.AsyncClient(
            timeout=resolved.http_timeout_seconds,
            headers={"User-Agent": "oshiloot/0.1"},
        )
        app.state.cache, app.state.clicks = build_storage(resolved)
        yield
        await app.state.http.aclose()

    configure_logging()
    app = FastAPI(
        title="OshiLoot API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(RequestLogMiddleware)

    for module in (anime, merch, music, regions, go):
        app.include_router(module.router)

    @app.get("/api/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
