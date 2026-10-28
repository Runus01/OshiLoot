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
