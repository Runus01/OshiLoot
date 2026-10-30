"""Search terms for one character's merch, and sorting listings into solo and group items.

Store search is keyword-based, so "Frieren Fern" finds everything that mentions Fern:
her own acrylic stand, but also the party's group poster. Listing titles name the
characters on the item, which is how a listing is sorted into "just Fern" or "Fern with
Stark and Frieren".
"""

import re
import unicodedata

from app.merch.models import CharacterQuery, Titles

# Kanji or hiragana in a native name means a Japanese name, romanised with long vowels
# ("Tanjirou Kamado", "Satoru Gojou"). Katakana-only names are usually foreign names
# ("Fern", "Stark"), which have no long vowels to drop.
_JAPANESE_NAME = re.compile(r"[぀-ゟ㐀-鿿]")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]+")


def fold(text: str) -> str:
    """Drop accents from Latin letters ("Übel" -> "Ubel"), as listings usually do, and
    unify full- and half-width forms. Japanese is untouched: its voicing marks matter."""
    kept: list[str] = []
    for char in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(char) and kept and kept[-1].isascii():
            continue
        kept.append(char)
    return unicodedata.normalize("NFKC", "".join(kept))


def short_title(title: str) -> str:
    """The part before a subtitle: "Frieren: Beyond Journey's End" -> "Frieren"."""
    return re.split(r"\s*[:：]\s*", title, maxsplit=1)[0].strip() or title


def merch_name(name: str, native: str | None) -> str:
    """How a character's name is usually spelled on merch listings.

    Listings drop the doubled vowels of strict romanisation ("Tanjiro", "Gojo"). Only an
    "ou" or "uu" that isn't followed by another vowel is shortened, so "Inoue" stays as is.
    """
    if not native or not _JAPANESE_NAME.search(native):
        return name
    name = re.sub(r"ou(?![aeiou])", "o", name)
    name = re.sub(r"Ou(?![aeiou])", "O", name)
    return re.sub(r"uu(?![aeiou])", "u", name, flags=re.IGNORECASE)


def character_term(term: str, titles: Titles, character: CharacterQuery) -> str:
    """The search term for a store that searches in English ("en") or Japanese ("ja")."""
    if term == "ja":
        title = short_title(titles.ja or titles.main)
        name = character.name_ja or character.name
    else:
        title = short_title(titles.en or titles.main)
        name = merch_name(character.name, character.name_ja)
    # Title characters ("Frieren" in "Frieren") need no second mention.
    if name.casefold() in title.casefold():
        return title
    return f"{title} {name}"


def _tokens(name: str, native: str | None) -> set[str]:
    words = {w.casefold() for w in _WORD.findall(fold(f"{name} {merch_name(name, native)}"))}
    tokens = {w for w in words if len(w) >= 3}
    if native and len(native) >= 2:
        tokens.add(fold(native).replace(" ", "").replace("・", ""))
    return tokens


class CastMatcher:
    """Finds which other cast members a listing title names.

    A word counts only if it belongs to one cast member: the Forger family share
    "Forger", so it can't tell Anya's listing from Loid's. Words in the anime's own title
    are ignored too ("Frieren" names both the show and its heroine).
    """

    def __init__(self, character: CharacterQuery, titles: Titles) -> None:
        title_words = fold(" ".join(t for t in (titles.main, titles.en, titles.ja) if t)).casefold()
        members = [(character.name, character.name_ja)] + [
            (m.name, m.name_ja) for m in character.cast if m.name != character.name
        ]
        owners: dict[str, set[int]] = {}
        for index, (name, native) in enumerate(members):
            for token in _tokens(name, native):
                if token in title_words:
                    continue
                owners.setdefault(token, set()).add(index)
        self._names = [name for name, _ in members]
        self._patterns = [
            (next(iter(who)), self._pattern(token))
            for token, who in owners.items()
            if len(who) == 1 and next(iter(who)) != 0  # 0 is the character searched for
        ]

    @staticmethod
    def _pattern(token: str) -> re.Pattern[str]:
        if token.isascii():
            return re.compile(rf"(?<![a-z]){re.escape(token)}(?![a-z])", re.IGNORECASE)
        return re.compile(re.escape(token))

    def others_in(self, listing_title: str) -> list[str]:
        title = fold(listing_title)
        found = {index for index, pattern in self._patterns if pattern.search(title)}
        return [self._names[i] for i in sorted(found)]
