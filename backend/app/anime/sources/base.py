from typing import Protocol

from app.anime.models import Anime, Character, ListEntry, ListStatus, Themes


class AnimeSourceError(Exception):
    """The upstream anime database failed or rejected the request."""


class UserNotFound(AnimeSourceError):
    """No public list for this username (wrong name, or the list is private)."""


class SourceNotConfigured(AnimeSourceError):
    """Credentials for the upstream are missing."""


class AccessTokenRejected(AnimeSourceError):
    """The signed-in user's access token is expired or revoked."""


class CharacterSourceError(AnimeSourceError):
    """The character database (AniList) failed or rejected the request."""


class CharacterSourceBusy(CharacterSourceError):
    """The character database is rate-limiting us; worth retrying in a minute."""


class AnimeSource(Protocol):
    """Anything that can supply anime data. MyAnimeList today."""

    async def user_list(self, username: str, status: ListStatus) -> list[ListEntry]: ...
    async def search(self, query: str, limit: int) -> list[Anime]: ...
    async def get(self, anime_id: int) -> Anime | None: ...
    async def themes(self, anime_id: int) -> Themes | None: ...


class CharacterSource(Protocol):
    """Characters, looked up by MyAnimeList anime ID. AniList today."""

    async def characters(self, mal_id: int, page: int) -> tuple[list[Character], bool]: ...
    async def character(self, character_id: int) -> Character | None: ...
