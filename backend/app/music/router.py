from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from app.core.config import Settings
from app.core.deps import get_cache, get_http, get_settings
from app.core.storage import KeyValueStore
from app.music.itunes import ItunesClient
from app.music.models import SongQuery, SongResponse
from app.music.service import MusicService, load_music_stores

router = APIRouter(prefix="/api/music", tags=["music"])


def get_service(
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    cache: Annotated[KeyValueStore, Depends(get_cache)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MusicService:
    return MusicService(ItunesClient(http), load_music_stores(), cache, settings)


Text = Annotated[str, Query(min_length=1, max_length=200)]
OptionalText = Annotated[str | None, Query(max_length=200)]


@router.get("/song", response_model=SongResponse)
async def song(
    service: Annotated[MusicService, Depends(get_service)],
    anime_id: Annotated[int, Query(gt=0)],
    title: Text,
    artist: Text,
    country: Annotated[str, Query(pattern=r"^[A-Z]{2}$")],
    title_native: OptionalText = None,
    artist_native: OptionalText = None,
    theme_id: Annotated[int | None, Query(gt=0)] = None,
) -> SongResponse:
    """Where to hear and buy a theme song. The browser sends the song details it got from
    the anime module, so this module never calls it."""
    query = SongQuery(
        title=title,
        title_native=title_native or None,
        artist=artist,
        artist_native=artist_native or None,
    )
    return await service.find(query, country, anime_id, theme_id)
