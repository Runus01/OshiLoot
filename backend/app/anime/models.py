from typing import Literal

from pydantic import BaseModel

ListStatus = Literal["completed", "watching"]


class AnimeTitles(BaseModel):
    main: str
    en: str | None = None
    ja: str | None = None
    synonyms: list[str] = []


class Anime(BaseModel):
    id: int
    titles: AnimeTitles
    picture: str | None = None
    mean_score: float | None = None
    media_type: str | None = None


class ListEntry(BaseModel):
    anime: Anime
    status: str
    score: int  # 1-10, or 0 when the user hasn't scored it


class MyLists(BaseModel):
    """Both lists of the signed-in user, fetched in one request so a token refresh
    happens once (MAL revokes the old refresh token each time)."""

    username: str
    completed: list[ListEntry]
    watching: list[ListEntry]


class SignInStatus(BaseModel):
    available: bool  # is sign-in configured on this server?
    signed_in: bool
    username: str | None = None
