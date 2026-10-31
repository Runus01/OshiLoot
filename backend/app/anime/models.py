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


Season = Literal["winter", "spring", "summer", "fall"]


class SeasonalAnime(BaseModel):
    """Anime that premiered this season, the most-listed on MyAnimeList first."""

    year: int
    season: Season
    anime: list[Anime]


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


CharacterRole = Literal["main", "supporting", "background"]


class Character(BaseModel):
    """A character, from AniList. id is AniList's character ID."""

    id: int
    name: str
    name_native: str | None = None
    alternative: list[str] = []
    image: str | None = None
    role: CharacterRole | None = None  # their role in this anime; None when looked up alone


class CharacterPage(BaseModel):
    anime_id: int
    page: int
    characters: list[Character]
    has_next_page: bool


ThemeKind = Literal["opening", "ending"]


class ThemeSong(BaseModel):
    """An opening or ending theme, parsed from MyAnimeList's one-line description:
    #1: "Yuusha (勇者)" by YOASOBI (eps 1-16)"""

    id: int  # MyAnimeList's theme ID
    kind: ThemeKind
    number: str | None = None  # "1", or "S1" for specials
    title: str
    title_native: str | None = None
    artist: str
    artist_native: str | None = None
    episodes: str | None = None  # "eps 1-16"
    text: str  # MyAnimeList's original line


class Themes(BaseModel):
    anime_id: int
    openings: list[ThemeSong]
    endings: list[ThemeSong]
