"""Turn MyAnimeList's opening/ending lines into title, artist and episodes.

MAL describes each theme as one line of text, in a fairly consistent shape:

    #1: "Yuusha (勇者)" by YOASOBI (eps 1-16)
    #2: "Haru (晴る)" by Yorushika (ヨルシカ) (eps 17-28)
    #S1: "bliss" by milet (eps Special Broadcast: 1-4)
    "Kaikai Kitan" by Eve

Lines that don't fit keep their full text as the title, so nothing is lost.
"""

import re
from typing import Any

from app.anime.models import ThemeKind, ThemeSong

_LINE = re.compile(
    r"""^\s*(?:\#?(?P<number>[A-Za-z]*\d+)\s*:\s*)?   # #1: or #S1:
        "(?P<title>.+)"\s+by\s+                       # "Title" by
        (?P<artist>.+?)                               # Artist (ネイティブ)
        (?:\s+\((?P<episodes>eps?\b[^)]*)\))?\s*$     # (eps 1-16)
    """,
    re.VERBOSE,
)
_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
_TRAILING_PARENS = re.compile(r"^(?P<main>.*?)\s*\((?P<inner>[^()]*)\)\s*$")


def _split_native(text: str) -> tuple[str, str | None]:
    """ "Yuusha (勇者)" -> ("Yuusha", "勇者"). Parentheses without Japanese are kept."""
    match = _TRAILING_PARENS.match(text)
    if not match or not match["main"] or _JAPANESE.search(match["main"]):
        return text.strip(), None
    # MAL sometimes adds a translation: "Gurenge (紅蓮華; Crimson Lotus)"
    parts = [p.strip() for p in re.split(r"[;/]", match["inner"])]
    native = next((p for p in parts if _JAPANESE.search(p)), None)
    if native is None:
        return text.strip(), None
    return match["main"].strip(), native


def parse_theme(raw: dict[str, Any], kind: ThemeKind) -> ThemeSong:
    text = str(raw.get("text") or "").strip()
    match = _LINE.match(text)
    if not match:
        return ThemeSong(id=int(raw["id"]), kind=kind, title=text.strip('"'), artist="", text=text)
    title, title_native = _split_native(match["title"])
    artist, artist_native = _split_native(match["artist"])
    return ThemeSong(
        id=int(raw["id"]),
        kind=kind,
        number=match["number"],
        title=title,
        title_native=title_native,
        artist=artist,
        artist_native=artist_native,
        episodes=match["episodes"],
        text=text,
    )
