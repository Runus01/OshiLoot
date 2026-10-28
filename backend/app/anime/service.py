from app.anime.models import Anime, ListEntry, ListStatus
from app.anime.sources.base import AnimeSource
from app.core.storage import KeyValueStore

DAY = 24 * 60 * 60


class AnimeService:
    def __init__(self, source: AnimeSource, cache: KeyValueStore) -> None:
        self._source = source
        self._cache = cache

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
