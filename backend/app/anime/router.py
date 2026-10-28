from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from app.anime.models import Anime, ListEntry, ListStatus
from app.anime.service import AnimeService
from app.anime.sources.base import AnimeSource, AnimeSourceError, SourceNotConfigured, UserNotFound
from app.anime.sources.mal import MalSource
from app.core.config import Settings
from app.core.deps import get_cache, get_http, get_settings
from app.core.storage import KeyValueStore

router = APIRouter(prefix="/api/anime", tags=["anime"])


def get_source(
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnimeSource:
    return MalSource(http, settings.mal_client_id)


def get_service(
    source: Annotated[AnimeSource, Depends(get_source)],
    cache: Annotated[KeyValueStore, Depends(get_cache)],
) -> AnimeService:
    return AnimeService(source, cache)


Service = Annotated[AnimeService, Depends(get_service)]


def upstream_error(exc: AnimeSourceError) -> HTTPException:
    if isinstance(exc, UserNotFound):
        return HTTPException(
            404,
            "No public list found for that username. Check the spelling, "
            "or make your list public in your MyAnimeList settings.",
        )
    if isinstance(exc, SourceNotConfigured):
        return HTTPException(503, "MyAnimeList isn't configured on this server (MAL_CLIENT_ID).")
    return HTTPException(502, "MyAnimeList didn't respond. Try again in a minute.")


@router.get("/users/{username}/list", response_model=list[ListEntry])
async def user_list(
    username: Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{2,16}$")],
    service: Service,
    response: Response,
    status: ListStatus = "completed",
) -> list[ListEntry]:
    response.headers["Cache-Control"] = "no-store"
    try:
        return await service.user_list(username, status)
    except AnimeSourceError as exc:
        raise upstream_error(exc) from exc


@router.get("/search", response_model=list[Anime])
async def search(
    service: Service, q: Annotated[str, Query(min_length=3, max_length=100)]
) -> list[Anime]:
    try:
        return await service.search(q)
    except AnimeSourceError as exc:
        raise upstream_error(exc) from exc


@router.get("/{anime_id}", response_model=Anime)
async def details(anime_id: Annotated[int, Path(gt=0)], service: Service) -> Anime:
    try:
        anime = await service.get(anime_id)
    except AnimeSourceError as exc:
        raise upstream_error(exc) from exc
    if anime is None:
        raise HTTPException(404, "No anime with that ID.")
    return anime
