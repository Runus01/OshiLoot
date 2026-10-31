from datetime import datetime

from app.anime.models import (
    Anime,
    Character,
    CharacterPage,
    ListEntry,
    ListStatus,
    SeasonalAnime,
    Themes,
)
from app.anime.seasons import current_season
from app.anime.sources.base import AnimeSource, CharacterSource
from app.core.storage import KeyValueStore

HOUR = 60 * 60
DAY = 24 * HOUR
ROW_SIZE = 24  # covers in each row on the home page


class AnimeService:
    def __init__(
        self,
        source: AnimeSource,
        cache: KeyValueStore,
        characters: CharacterSource | None = None,
    ) -> None:
        self._source = source
        self._cache = cache
        self._characters = characters

    async def user_list(self, username: str, status: ListStatus) -> list[ListEntry]:
        # Never cached: MAL's terms bar storing users' list data on the server.
        return await self._source.user_list(username, status)

    async def search(self, query: str, limit: int = 20) -> list[Anime]:
        key = f"anime:search:{limit}:{query.strip().lower()}"
        if (cached := await self._cache.get(key)) is not None:
            return [Anime.model_validate(a) for a in cached]
        results = await self._source.search(query.strip(), limit)
        await self._cache.put(key, [a.model_dump() for a in results], DAY)
        return results

    async def get(self, anime_id: int) -> Anime | None:
        key = f"anime:{anime_id}"
        if (cached := await self._cache.get(key)) is not None:
            return Anime.model_validate(cached)
        anime = await self._source.get(anime_id)
        if anime is not None:
            await self._cache.put(key, anime.model_dump(), DAY)
        return anime

    async def seasonal(self, now: datetime | None = None) -> SeasonalAnime:
        """This season's new anime for the home page. Rankings shift through the season,
        so they're refreshed every six hours."""
        year, season = current_season(now)
        key = f"anime:season:{year}:{season}:{ROW_SIZE}"
        if (cached := await self._cache.get(key)) is not None:
            return SeasonalAnime.model_validate(cached)
        # Asks for more than a row, because carried-over shows and promos are left out.
        premiered = await self._source.seasonal(year, season, 100)
        result = SeasonalAnime(year=year, season=season, anime=premiered[:ROW_SIZE])
        await self._cache.put(key, result.model_dump(), 6 * HOUR)
        return result

    async def popular(self) -> list[Anime]:
        """The all-time most popular anime for the home page."""
        key = f"anime:popular:{ROW_SIZE}"
        if (cached := await self._cache.get(key)) is not None:
            return [Anime.model_validate(a) for a in cached]
        anime = await self._source.popular(ROW_SIZE)
        await self._cache.put(key, [a.model_dump() for a in anime], DAY)
        return anime

    async def themes(self, anime_id: int) -> Themes | None:
        key = f"anime:themes:{anime_id}"
        if (cached := await self._cache.get(key)) is not None:
            return Themes.model_validate(cached)
        themes = await self._source.themes(anime_id)
        if themes is not None:
            await self._cache.put(key, themes.model_dump(), DAY)
        return themes

    # Characters come from AniList, which allows 30 requests a minute, so each page is
    # cached for a day. That's a short-lived cache, not the bulk copy AniList's terms forbid.

    async def characters(self, anime_id: int, page: int) -> CharacterPage:
        key = f"anime:characters:{anime_id}:{page}"
        if (cached := await self._cache.get(key)) is not None:
            return CharacterPage.model_validate(cached)
        if self._characters is None:
            return CharacterPage(anime_id=anime_id, page=page, characters=[], has_next_page=False)
        characters, has_next = await self._characters.characters(anime_id, page)
        result = CharacterPage(
            anime_id=anime_id, page=page, characters=characters, has_next_page=has_next
        )
        await self._cache.put(key, result.model_dump(), DAY)
        return result

    async def character(self, character_id: int) -> Character | None:
        key = f"anime:character:{character_id}"
        if (cached := await self._cache.get(key)) is not None:
            return Character.model_validate(cached)
        if self._characters is None:
            return None
        character = await self._characters.character(character_id)
        if character is not None:
            await self._cache.put(key, character.model_dump(), DAY)
        return character
