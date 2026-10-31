"""MyAnimeList API v2 client.

Public data needs only the X-MAL-CLIENT-ID header. With a signed-in user's access token,
the same calls also see private lists (use the username "@me").
"""

from typing import Any

import httpx

from app.anime.models import Anime, AnimeTitles, ListEntry, ListStatus, Season, Themes
from app.anime.sources.base import (
    AccessTokenRejected,
    AnimeSourceError,
    SourceNotConfigured,
    UserNotFound,
)
from app.anime.themes import parse_theme

MAL_API = "https://api.myanimelist.net/v2"
ANIME_FIELDS = "alternative_titles,main_picture,mean,media_type"
# Music videos and promos can rank among a season's most-listed entries; they have no merch.
NOT_SHOWS = {"music", "pv", "cm"}


def _to_anime(node: dict[str, Any]) -> Anime:
    alt = node.get("alternative_titles") or {}
    picture = node.get("main_picture") or {}
    return Anime(
        id=node["id"],
        titles=AnimeTitles(
            main=node["title"],
            en=alt.get("en") or None,
            ja=alt.get("ja") or None,
            synonyms=alt.get("synonyms") or [],
        ),
        picture=picture.get("large") or picture.get("medium"),
        mean_score=node.get("mean"),
        media_type=node.get("media_type"),
    )


class MalSource:
    def __init__(
        self, http: httpx.AsyncClient, client_id: str, access_token: str | None = None
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._access_token = access_token

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        if not self._client_id:
            raise SourceNotConfigured("MAL_CLIENT_ID is not set")
        headers = {"X-MAL-CLIENT-ID": self._client_id}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        try:
            response = await self._http.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise AnimeSourceError("MyAnimeList did not respond") from exc
        if response.status_code == 401:
            if self._access_token:
                raise AccessTokenRejected("MyAnimeList rejected the access token")
            raise AnimeSourceError("MyAnimeList rejected the client ID")
        return response

    async def user_list(self, username: str, status: ListStatus) -> list[ListEntry]:
        # MAL API agreement 3(c): user list data is passed through, never stored or logged.
        url: str | None = f"{MAL_API}/users/{username}/animelist"
        params: dict[str, Any] | None = {
            "status": status,
            "sort": "list_score",
            "limit": 1000,
            "fields": f"list_status,{ANIME_FIELDS}",
        }
        entries: list[ListEntry] = []
        while url:
            response = await self._get(url, params)
            if response.status_code in (403, 404):
                raise UserNotFound(username)
            if response.status_code != 200:
                raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
            body = response.json()
            for item in body.get("data", []):
                list_status = item.get("list_status") or {}
                entries.append(
                    ListEntry(
                        anime=_to_anime(item["node"]),
                        status=list_status.get("status", status),
                        score=int(list_status.get("score") or 0),
                    )
                )
            url, params = (body.get("paging") or {}).get("next"), None
        return entries

    async def search(self, query: str, limit: int) -> list[Anime]:
        response = await self._get(
            f"{MAL_API}/anime", {"q": query, "limit": limit, "fields": ANIME_FIELDS}
        )
        if response.status_code == 400:
            return []  # MAL rejects some very short or unusual queries
        if response.status_code != 200:
            raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
        return [_to_anime(item["node"]) for item in response.json().get("data", [])]

    async def get(self, anime_id: int) -> Anime | None:
        response = await self._get(f"{MAL_API}/anime/{anime_id}", {"fields": ANIME_FIELDS})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
        return _to_anime(response.json())

    async def seasonal(self, year: int, season: Season, limit: int) -> list[Anime]:
        """Anime that premiered in this season, most-listed first. Shows that started in an
        earlier season and are still running are left out, as are music videos and promos."""
        response = await self._get(
            f"{MAL_API}/anime/season/{year}/{season}",
            {
                "sort": "anime_num_list_users",
                "limit": limit,
                "fields": f"{ANIME_FIELDS},start_season",
            },
        )
        if response.status_code != 200:
            raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
        premiered: list[Anime] = []
        for item in response.json().get("data", []):
            node = item["node"]
            start = node.get("start_season") or {}
            if start and (start.get("year"), start.get("season")) != (year, season):
                continue
            if node.get("media_type") in NOT_SHOWS:
                continue
            premiered.append(_to_anime(node))
        return premiered

    async def popular(self, limit: int) -> list[Anime]:
        """The anime on the most MyAnimeList lists, all time."""
        response = await self._get(
            f"{MAL_API}/anime/ranking",
            {"ranking_type": "bypopularity", "limit": limit, "fields": ANIME_FIELDS},
        )
        if response.status_code != 200:
            raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
        return [_to_anime(item["node"]) for item in response.json().get("data", [])]

    async def themes(self, anime_id: int) -> Themes | None:
        # Not in MAL's API docs, but the anime endpoint returns both fields when asked.
        response = await self._get(
            f"{MAL_API}/anime/{anime_id}", {"fields": "opening_themes,ending_themes"}
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise AnimeSourceError(f"MyAnimeList returned {response.status_code}")
        body = response.json()
        return Themes(
            anime_id=anime_id,
            openings=[parse_theme(t, "opening") for t in body.get("opening_themes") or []],
            endings=[parse_theme(t, "ending") for t in body.get("ending_themes") or []],
        )
