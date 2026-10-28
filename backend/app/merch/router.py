from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from app.core.config import Settings
from app.core.deps import get_cache, get_http, get_settings
from app.core.storage import KeyValueStore
from app.merch.adapters.base import StoreAdapter
from app.merch.adapters.ebay import EbayAdapter
from app.merch.catalog import load_catalog
from app.merch.models import MerchResponse, Titles
from app.merch.service import MerchService

router = APIRouter(prefix="/api/merch", tags=["merch"])


def get_adapters(
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, StoreAdapter]:
    return {"ebay": EbayAdapter(http, settings)}


def get_service(
    adapters: Annotated[dict[str, StoreAdapter], Depends(get_adapters)],
    cache: Annotated[KeyValueStore, Depends(get_cache)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MerchService:
    return MerchService(load_catalog(), adapters, cache, settings)


@router.get("", response_model=MerchResponse)
async def find_merch(
    service: Annotated[MerchService, Depends(get_service)],
    anime_id: Annotated[int, Query(gt=0)],
    title: Annotated[str, Query(min_length=1, max_length=200)],
    country: Annotated[str, Query(pattern=r"^[A-Z]{2}$")],
    title_en: Annotated[str | None, Query(max_length=200)] = None,
    title_ja: Annotated[str | None, Query(max_length=200)] = None,
) -> MerchResponse:
    """The browser sends the titles it already has, so this module never calls the anime module."""
    titles = Titles(main=title, en=title_en or None, ja=title_ja or None)
    return await service.find(anime_id, titles, country)
