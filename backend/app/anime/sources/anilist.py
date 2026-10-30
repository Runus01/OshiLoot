"""AniList GraphQL API: characters, looked up by MyAnimeList anime ID.

MyAnimeList's official API has no characters, and AniList stores each anime's MAL ID,
so no ID mapping is needed. Terms: https://docs.anilist.co/guide/terms-of-use (free for
commercial use under US$150 revenue a month; no bulk collection). The API allows 30
requests a minute at the moment, so results are cached (see AnimeService).
"""

from typing import Any

import httpx

from app.anime.models import Character, CharacterRole
from app.anime.sources.base import CharacterSourceBusy, CharacterSourceError

ANILIST_API = "https://graphql.anilist.co"
PER_PAGE = 25  # AniList's maximum page size

_NAME = "id name { full native alternative } image { large }"

CHARACTERS_QUERY = f"""
query ($idMal: Int, $page: Int, $perPage: Int) {{
  Media(idMal: $idMal, type: ANIME) {{
    characters(page: $page, perPage: $perPage, sort: [ROLE, RELEVANCE, ID]) {{
      pageInfo {{ hasNextPage }}
      edges {{ role node {{ {_NAME} }} }}
    }}
  }}
}}
"""

CHARACTER_QUERY = f"query ($id: Int) {{ Character(id: $id) {{ {_NAME} }} }}"

ROLES: dict[str, CharacterRole] = {
    "MAIN": "main",
    "SUPPORTING": "supporting",
    "BACKGROUND": "background",
}


def _to_character(node: dict[str, Any], role: str | None = None) -> Character:
    name = node.get("name") or {}
    image = (node.get("image") or {}).get("large")
    return Character(
        id=node["id"],
        name=name.get("full") or name.get("native") or "Unknown",
        name_native=name.get("native") or None,
        alternative=[a for a in name.get("alternative") or [] if a],
        # AniList serves a grey silhouette when it has no picture; show our own blank instead.
        image=None if not image or image.endswith("/default.jpg") else image,
        role=ROLES.get(role or ""),
    )


class AniListSource:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def _query(self, query: str, variables: dict[str, Any]) -> dict[str, Any] | None:
        """Run a query. Returns its data, or None when AniList has no such entry."""
        try:
            response = await self._http.post(
                ANILIST_API,
                json={"query": query, "variables": variables},
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise CharacterSourceError("AniList did not respond") from exc
        if response.status_code == 429:
            raise CharacterSourceBusy("AniList rate limit reached")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise CharacterSourceError(f"AniList returned {response.status_code}")
        body = response.json()
        if body.get("errors"):
            raise CharacterSourceError(f"AniList error: {body['errors'][0].get('message')}")
        return body.get("data")

    async def characters(self, mal_id: int, page: int) -> tuple[list[Character], bool]:
        data = await self._query(
            CHARACTERS_QUERY, {"idMal": mal_id, "page": page, "perPage": PER_PAGE}
        )
        media = (data or {}).get("Media")
        if not media:
            return [], False
        connection = media.get("characters") or {}
        characters = [
            _to_character(edge["node"], edge.get("role"))
            for edge in connection.get("edges") or []
            if edge.get("node")
        ]
        return characters, bool((connection.get("pageInfo") or {}).get("hasNextPage"))

    async def character(self, character_id: int) -> Character | None:
        data = await self._query(CHARACTER_QUERY, {"id": character_id})
        node = (data or {}).get("Character")
        return _to_character(node) if node else None
