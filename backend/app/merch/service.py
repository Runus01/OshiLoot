import asyncio
import logging
from collections.abc import Mapping, Sequence

from app.core.config import Settings
from app.core.signing import sign
from app.core.storage import KeyValueStore
from app.merch.adapters.base import StoreAdapter
from app.merch.catalog import StoreDef
from app.merch.models import MerchResponse, StoreResult, Titles

logger = logging.getLogger(__name__)

CACHE_SECONDS = 6 * 60 * 60


class MerchService:
    def __init__(
        self,
        catalog: Sequence[StoreDef],
        adapters: Mapping[str, StoreAdapter],
        cache: KeyValueStore,
        settings: Settings,
    ) -> None:
        self._catalog = catalog
        self._adapters = adapters
        self._cache = cache
        self._settings = settings

    async def find(self, anime_id: int, titles: Titles, country: str) -> MerchResponse:
        key = f"merch:{anime_id}:{country}"
        if (cached := await self._cache.get(key)) is not None:
            return MerchResponse.model_validate(cached)

        stores = [s for s in self._catalog if s.available_in(country)]
        results = await asyncio.gather(*(self._search(s, titles, country) for s in stores))
        response = MerchResponse(
            anime_id=anime_id,
            country=country,
            stores=[self._signed(r, anime_id, country) for r in results],
        )
        # Don't keep a degraded answer for six hours: only cache when no store failed.
        if all(r.status in ("ok", "not_configured") for r in results):
            await self._cache.put(key, response.model_dump(), CACHE_SECONDS)
        return response

    async def _search(self, store: StoreDef, titles: Titles, country: str) -> StoreResult:
        term = store.term_for(titles)
        search_url = store.search_url_for(country, term)
        affiliate = False
        if search_url:
            search_url, affiliate = store.affiliate_wrap(search_url, self._settings)
        result = StoreResult(
            store=store.id,
            name=store.name,
            kind=store.kind,
            status="ok",
            search_url=search_url,
            search_term=term,
            affiliate=affiliate,
        )
        if store.type == "linkout":
            return result

        adapter = self._adapters.get(store.id)
        if adapter is None or not adapter.configured:
            result.status = "not_configured"
            return result
        try:
            result.offers = await asyncio.wait_for(
                adapter.search(term, country), self._settings.store_deadline_seconds
            )
            result.affiliate = adapter.affiliate
        except TimeoutError:
            result.status = "timeout"
        except Exception:
            logger.exception("store search failed: %s", store.id)
            result.status = "error"
        return result

    def _signed(self, result: StoreResult, anime_id: int, country: str) -> StoreResult:
        """Replace every outbound URL with /go/<signed token> so clicks are counted."""

        def go(url: str) -> str:
            token = sign(
                {"u": url, "s": result.store, "a": anime_id, "c": country},
                self._settings.link_signing_key,
            )
            return f"/go/{token}"

        result.offers = [o.model_copy(update={"url": go(o.url)}) for o in result.offers]
        if result.search_url:
            result.search_url = go(result.search_url)
        return result
