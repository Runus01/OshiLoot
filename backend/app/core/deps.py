"""FastAPI dependencies for the shared resources created at startup (see app.main)."""

import httpx
from fastapi import Request

from app.core.config import Settings
from app.core.storage import EventLog, KeyValueStore


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


def get_cache(request: Request) -> KeyValueStore:
    return request.app.state.cache


def get_clicks(request: Request) -> EventLog:
    return request.app.state.clicks
