import hashlib
import json
import logging
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import yaml
from pydantic import BaseModel

from app.core.config import Settings
from app.core.links import affiliate_url, go_link, search_url
from app.core.storage import KeyValueStore
from app.music.itunes import AppleBusy, AppleError, ItunesClient, pick
from app.music.models import (
    AppleStatus,
    AppleTrack,
    DigitalRelease,
    MusicStore,
    SongQuery,
    SongResponse,
)

logger = logging.getLogger(__name__)

DAY = 24 * 60 * 60


class MusicStoreDef(BaseModel):
    id: str
    name: str
    note: str | None = None
    term: Literal["en", "ja"] = "ja"
    search_url: str
    affiliate_template_setting: str | None = None

    def term_for(self, song: SongQuery) -> str:
        if self.term == "ja":
            return f"{song.artist_native or song.artist} {song.title_native or song.title}"
        return f"{song.artist} {song.title}"


@lru_cache
def load_music_stores() -> tuple[MusicStoreDef, ...]:
    data = yaml.safe_load(Path(__file__).with_name("stores.yaml").read_text(encoding="utf-8"))
    return tuple(MusicStoreDef.model_validate(s) for s in data["stores"])


class AppleLookup(BaseModel):
    status: AppleStatus
    track: AppleTrack | None = None
    releases: list[DigitalRelease] = []


class MusicService:
    def __init__(
        self,
        itunes: ItunesClient,
        stores: Sequence[MusicStoreDef],
        cache: KeyValueStore,
        settings: Settings,
    ) -> None:
        self._itunes = itunes
        self._stores = stores
        self._cache = cache
        self._settings = settings

    async def find(
        self, song: SongQuery, country: str, anime_id: int, theme_id: int | None
    ) -> SongResponse:
        apple = await self._lookup(song, country)
        clicks: dict[str, Any] = {"a": anime_id, "c": country}
        if theme_id:
            clicks["th"] = theme_id

        def go(url: str, store: str) -> str:
            return go_link(url, {"s": store, **clicks}, self._settings.link_signing_key)

        track = apple.track
        if track:
            track = track.model_copy(update={"url": go(self._apple_link(track.url), "apple")})
        releases = [
            r.model_copy(update={"url": go(self._apple_link(r.url), "apple")})
            for r in apple.releases
        ]
        apple_search = self._apple_link(
            f"https://music.apple.com/{country.lower()}/search?term="
            + quote(f"{song.artist} {song.title}", safe="")
        )
        return SongResponse(
            country=country,
            apple_status=apple.status,
            track=track,
            releases=releases,
            apple_search_url=go(apple_search, "apple"),
            stores=[self._store(s, song, go) for s in self._stores],
        )

    async def _lookup(self, song: SongQuery, country: str) -> AppleLookup:
        digest = hashlib.sha1(song.model_dump_json().encode(), usedforsecurity=False)
        key = f"music:apple:{country}:{digest.hexdigest()}"
        if (cached := await self._cache.get(key)) is not None:
            return AppleLookup.model_validate(cached)

        terms = [f"{song.artist} {song.title}"]
        if song.title_native:
            terms.append(f"{song.artist_native or song.artist} {song.title_native}")
        result = AppleLookup(status="not_found")
        try:
            for term in dict.fromkeys(terms):  # drop duplicates, keep order
                track, releases = pick(await self._itunes.search(term, country), song)
                if track:
                    result = AppleLookup(status="ok", track=track, releases=releases)
                    break
        except AppleBusy:
            return AppleLookup(status="busy")
        except AppleError:
            logger.exception("Apple search failed")
            return AppleLookup(status="error")
        # Search results may be cached (Apple asks large sites to); the audio itself isn't.
        await self._cache.put(key, json.loads(result.model_dump_json()), DAY)
        return result

    def _apple_link(self, url: str) -> str:
        """Add the Apple affiliate token, when there is one, to an Apple Music/iTunes link."""
        token = self._settings.apple_affiliate_token
        if not token:
            return url
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k not in ("at", "ct", "app")]
        query += [("at", token), ("ct", "oshiloot"), ("app", "music")]
        return urlunsplit(parts._replace(query=urlencode(query)))

    def _store(self, store: MusicStoreDef, song: SongQuery, go: Any) -> MusicStore:
        term = store.term_for(song)
        url = search_url(store.search_url, term)
        template = getattr(self._settings, store.affiliate_template_setting or "", "") or ""
        url, affiliate = affiliate_url(url, template)
        return MusicStore(
            store=store.id,
            name=store.name,
            note=store.note,
            search_url=go(url, store.id),
            search_term=term,
            affiliate=affiliate,
        )
