from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import Settings
from app.core.deps import get_cache, get_http, get_settings
from app.core.storage import KeyValueStore
from app.merch.adapters.base import StoreAdapter
from app.merch.adapters.ebay import EbayAdapter
from app.merch.catalog import load_catalog, load_shops
from app.merch.models import CastMember, CharacterQuery, MerchResponse, Titles
from app.merch.service import MerchService

router = APIRouter(prefix="/api/merch", tags=["merch"])

MAX_CAST = 50


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
    return MerchService(load_catalog(), adapters, cache, settings, load_shops())


Service = Annotated[MerchService, Depends(get_service)]
AnimeId = Annotated[int, Query(gt=0)]
Title = Annotated[str, Query(min_length=1, max_length=200)]
OptionalTitle = Annotated[str | None, Query(max_length=200)]
Country = Annotated[str, Query(pattern=r"^[A-Z]{2}$")]


@router.get("", response_model=MerchResponse)
async def find_merch(
    service: Service,
    anime_id: AnimeId,
    title: Title,
    country: Country,
    title_en: OptionalTitle = None,
    title_ja: OptionalTitle = None,
) -> MerchResponse:
    """The browser sends the titles it already has, so this module never calls the anime module."""
    titles = Titles(main=title, en=title_en or None, ja=title_ja or None)
    return await service.find(anime_id, titles, country)


@router.get("/character", response_model=MerchResponse)
async def find_character_merch(
    service: Service,
    anime_id: AnimeId,
    character_id: Annotated[int, Query(gt=0)],
    character: Annotated[str, Query(min_length=1, max_length=120)],
    title: Title,
    country: Country,
    character_ja: Annotated[str | None, Query(max_length=120)] = None,
    title_en: OptionalTitle = None,
    title_ja: OptionalTitle = None,
    cast: Annotated[list[str] | None, Query()] = None,
) -> MerchResponse:
    """Merch for one character. cast lists the anime's other characters as "Name|ネイティブ"
    (the native half is optional), so listings can be split into solo and group items."""
    entries = cast or []
    if len(entries) > MAX_CAST:
        raise HTTPException(422, f"Send at most {MAX_CAST} cast members.")
    members = []
    for entry in entries:
        name, _, native = entry.partition("|")
        if name.strip() and len(entry) <= 250:
            members.append(CastMember(name=name.strip(), name_ja=native.strip() or None))
    query = CharacterQuery(
        id=character_id, name=character, name_ja=character_ja or None, cast=members
    )
    titles = Titles(main=title, en=title_en or None, ja=title_ja or None)
    return await service.find_for_character(anime_id, titles, query, country)
