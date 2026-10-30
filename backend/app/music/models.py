from typing import Literal

from pydantic import BaseModel

AppleStatus = Literal["ok", "not_found", "busy", "error"]
ReleaseKind = Literal["single", "ep", "album"]


class SongQuery(BaseModel):
    title: str
    title_native: str | None = None
    artist: str
    artist_native: str | None = None


class Money(BaseModel):
    amount: float
    currency: str


class AppleTrack(BaseModel):
    """The matching song in the user's Apple store, with its 30-second preview."""

    name: str
    artist: str
    album: str
    artwork: str | None = None
    preview_url: str | None = None  # streamed from Apple; never stored (Apple's terms)
    url: str
    price: Money | None = None


class DigitalRelease(BaseModel):
    """A single, EP or album on Apple that includes the song."""

    name: str
    kind: ReleaseKind
    url: str
    artwork: str | None = None
    price: Money | None = None


class MusicStore(BaseModel):
    """A store selling CDs and vinyl, as a search link."""

    store: str
    name: str
    note: str | None = None
    search_url: str
    search_term: str
    affiliate: bool = False


class SongResponse(BaseModel):
    country: str
    apple_status: AppleStatus
    track: AppleTrack | None = None
    releases: list[DigitalRelease] = []
    apple_search_url: str  # Apple Music search, for when there's no exact match
    stores: list[MusicStore]
