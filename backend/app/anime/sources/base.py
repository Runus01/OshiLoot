from typing import Protocol

from app.anime.models import Anime, ListEntry, ListStatus


class AnimeSourceError(Exception):
    """The upstream anime database failed or rejected the request."""


class UserNotFound(AnimeSourceError):
    """No public list for this username (wrong name, or the list is private)."""


class SourceNotConfigured(AnimeSourceError):
    """Credentials for the upstream are missing."""


class AccessTokenRejected(AnimeSourceError):
    """The signed-in user's access token is expired or revoked."""


class AnimeSource(Protocol):
    """Anything that can supply anime data. MyAnimeList today; AniList could slot in here."""

    async def user_list(self, username: str, status: ListStatus) -> list[ListEntry]: ...
    async def search(self, query: str, limit: int) -> list[Anime]: ...
    async def get(self, anime_id: int) -> Anime | None: ...
