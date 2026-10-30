"""Apple's iTunes Search API: the song in the user's own Apple store, with a 30-second preview.

Docs and terms: https://performance-partners.apple.com/search-api
- About 20 requests a minute, so the service caches search results.
- Previews may only promote buying the song: shown beside an Apple badge, credited
  "courtesy of iTunes", and streamed, never downloaded or cached. The preview clip is
  Apple's choice; it is often, but not always, the chorus.
"""

import re
import unicodedata
from typing import Any

import httpx

from app.music.models import AppleTrack, DigitalRelease, Money, ReleaseKind, SongQuery

SEARCH_URL = "https://itunes.apple.com/search"

# Versions to avoid when a normal one exists: people want the song, not the karaoke track.
_ALTERNATE = re.compile(
    r"\b(instrumental|off[\s-]*vocal|karaoke|tv[\s-]*(size|ver)|anime[\s-]*(size|ver)"
    r"|remix|acoustic|live)\b"
    r"|TVサイズ|インスト|カラオケ|オフボーカル",
    re.IGNORECASE,
)
_BRACKETS = re.compile(r"[(\[（【].*?[)\]）】]|\s-\s.*$")


class AppleBusy(Exception):
    """Apple is rate-limiting this server."""


class AppleError(Exception):
    """Apple didn't answer properly."""


def _norm(text: str | None) -> str:
    """Compare titles loosely: width, case, brackets, punctuation and spaces don't matter."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _BRACKETS.sub("", text)
    return re.sub(r"[\W_]+", "", text)


def _same(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def _kind(collection: str) -> ReleaseKind:
    if collection.endswith(" - Single"):
        return "single"
    if collection.endswith(" - EP"):
        return "ep"
    return "album"


def _artwork(item: dict[str, Any]) -> str | None:
    art = item.get("artworkUrl100")
    return art.replace("100x100bb", "300x300bb") if art else None


def _money(value: Any, currency: str | None) -> Money | None:
    # Apple uses -1 for "not sold on its own" (album-only tracks).
    if not currency or not isinstance(value, int | float) or value < 0:
        return None
    return Money(amount=float(value), currency=currency)


class Match:
    """Scores Apple's search results against a song from MyAnimeList."""

    def __init__(self, song: SongQuery) -> None:
        self._titles = [t for t in (_norm(song.title), _norm(song.title_native)) if t]
        self._artists = [a for a in (_norm(song.artist), _norm(song.artist_native)) if a]

    def score(self, item: dict[str, Any]) -> float:
        artist = _norm(item.get("artistName"))
        if not any(_same(artist, a) for a in self._artists):
            return 0
        name = _norm(item.get("trackName"))
        if any(name == t for t in self._titles):
            score = 3.0
        elif any(_same(name, t) for t in self._titles):
            score = 2.0
        else:
            return 0
        if _ALTERNATE.search(f"{item.get('trackName', '')} {item.get('collectionName', '')}"):
            score -= 1.5
        if _kind(item.get("collectionName", "")) == "single":
            score += 0.25  # the single is usually the song's own release
        return score


class ItunesClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def search(self, term: str, country: str) -> list[dict[str, Any]]:
        try:
            response = await self._http.get(
                SEARCH_URL,
                params={
                    "term": term,
                    "country": country,
                    "media": "music",
                    "entity": "song",
                    "limit": 25,
                },
            )
        except httpx.HTTPError as exc:
            raise AppleError("Apple did not respond") from exc
        if response.status_code in (403, 429):
            raise AppleBusy(f"Apple returned {response.status_code}")
        if response.status_code != 200:
            raise AppleError(f"Apple returned {response.status_code}")
        try:
            return list(response.json().get("results") or [])
        except ValueError as exc:
            raise AppleError("Apple sent something other than JSON") from exc


def pick(
    results: list[dict[str, Any]], song: SongQuery
) -> tuple[AppleTrack | None, list[DigitalRelease]]:
    """The best matching track, and every release that has a matching version of it."""
    match = Match(song)
    scored = sorted(
        ((match.score(r), r) for r in results if r.get("kind") == "song"),
        key=lambda pair: pair[0],
        reverse=True,
    )
    scored = [(s, r) for s, r in scored if s >= 2]
    if not scored:
        return None, []
    best = scored[0][1]
    track = AppleTrack(
        name=best.get("trackName", song.title),
        artist=best.get("artistName", song.artist),
        album=best.get("collectionName", ""),
        artwork=_artwork(best),
        preview_url=best.get("previewUrl"),
        url=best.get("trackViewUrl", ""),
        price=_money(best.get("trackPrice"), best.get("currency")),
    )
    releases: dict[int, DigitalRelease] = {}
    for score, item in scored:
        collection_id = item.get("collectionId")
        if score < 2.5 or collection_id is None or collection_id in releases:
            continue  # skip karaoke and TV-size releases when listing what to buy
        name = item.get("collectionName", "")
        releases[collection_id] = DigitalRelease(
            name=re.sub(r" - (Single|EP)$", "", name),
            kind=_kind(name),
            url=item.get("collectionViewUrl", ""),
            artwork=_artwork(item),
            price=_money(item.get("collectionPrice"), item.get("currency")),
        )
    return track, list(releases.values())[:6]
