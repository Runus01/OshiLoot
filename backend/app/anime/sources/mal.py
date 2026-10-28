"""MyAnimeList API v2 client. Public data needs only the X-MAL-CLIENT-ID header."""

from typing import Any

import httpx

from app.anime.models import Anime, AnimeTitles, ListEntry, ListStatus
from app.anime.sources.base import AnimeSourceError, SourceNotConfigured, UserNotFound

MAL_API = "https://api.myanimelist.net/v2"
ANIME_FIELDS = "alternative_titles,main_picture,mean,media_type"


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
    def __init__(self, http: httpx.AsyncClient, client_id: str) -> None:
        self._http = http
        self._client_id = client_id

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        if not self._client_id:
            raise SourceNotConfigured("MAL_CLIENT_ID is not set")
        try:
            response = await self._http.get(
                url, params=params, headers={"X-MAL-CLIENT-ID": self._client_id}
            )
        except httpx.HTTPError as exc:
            raise AnimeSourceError("MyAnimeList did not respond") from exc
        if response.status_code == 401:
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
