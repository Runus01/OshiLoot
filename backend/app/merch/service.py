import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence

from app.core.config import Settings
from app.core.links import go_link, search_url
from app.core.storage import KeyValueStore
from app.merch.adapters.base import StoreAdapter
from app.merch.catalog import ShopDef, StoreDef
from app.merch.characters import CastMatcher, character_term, short_title
from app.merch.models import (
    CharacterQuery,
    MerchResponse,
    Offer,
    Outlet,
    ShopResult,
    StoreResult,
    Titles,
)

logger = logging.getLogger(__name__)

CACHE_SECONDS = 6 * 60 * 60


class MerchService:
    def __init__(
        self,
        catalog: Sequence[StoreDef],
        adapters: Mapping[str, StoreAdapter],
        cache: KeyValueStore,
        settings: Settings,
        shops: Mapping[str, Sequence[ShopDef]] | None = None,
    ) -> None:
        self._catalog = catalog
        self._adapters = adapters
        self._cache = cache
        self._settings = settings
        self._shops = shops or {}

    async def find(self, anime_id: int, titles: Titles, country: str) -> MerchResponse:
        return await self._find(
            key=f"merch:{anime_id}:{country}",
            anime_id=anime_id,
            character_id=None,
            country=country,
            term=lambda store: store.term_for(titles),
            shop_term=short_title(titles.en or titles.main),
        )

    async def find_for_character(
        self, anime_id: int, titles: Titles, character: CharacterQuery, country: str
    ) -> MerchResponse:
        matcher = CastMatcher(character, titles)
        return await self._find(
            key=f"merch:{anime_id}:character:{character.id}:{country}",
            anime_id=anime_id,
            character_id=character.id,
            country=country,
            term=lambda store: character_term(store.term, titles, character),
            shop_term=character_term("en", titles, character),
            tag=lambda offer: offer.model_copy(update={"others": matcher.others_in(offer.title)}),
        )

    async def _find(
        self,
        *,
        key: str,
        anime_id: int,
        character_id: int | None,
        country: str,
        term: Callable[[StoreDef], str],
        shop_term: str,
        tag: Callable[[Offer], Offer] | None = None,
    ) -> MerchResponse:
        if (cached := await self._cache.get(key)) is not None:
            return MerchResponse.model_validate(cached)

        stores = [s for s in self._catalog if s.available_in(country)]
        results = await asyncio.gather(*(self._search(s, term(s), country) for s in stores))
        if tag is not None:
            for result in results:
                result.offers = [tag(o) for o in result.offers]

        clicks = {"a": anime_id, "c": country} | ({"ch": character_id} if character_id else {})
        response = MerchResponse(
            anime_id=anime_id,
            character_id=character_id,
            country=country,
            stores=[self._signed(r, clicks) for r in results],
            shops=[self._shop(s, shop_term, clicks) for s in self._shops.get(country, ())],
        )
        # Don't keep a degraded answer for six hours: only cache when no store failed.
        if all(r.status in ("ok", "not_configured") for r in results):
            await self._cache.put(key, response.model_dump(), CACHE_SECONDS)
        return response

    async def _search(self, store: StoreDef, term: str, country: str) -> StoreResult:
        url = store.search_url_for(country, term)
        affiliate = False
        if url:
            url, affiliate = store.affiliate_wrap(url, self._settings)
        result = StoreResult(
            store=store.id,
            name=store.name,
            kind=store.kind,
            status="ok",
            search_url=url,
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

    def _go(self, url: str, store: str, clicks: dict[str, object]) -> str:
        return go_link(url, {"s": store, **clicks}, self._settings.link_signing_key)

    def _signed(self, result: StoreResult, clicks: dict[str, object]) -> StoreResult:
        """Replace every outbound URL with /go/<signed token> so clicks are counted."""
        result.offers = [
            o.model_copy(update={"url": self._go(o.url, result.store, clicks)})
            for o in result.offers
        ]
        if result.search_url:
            result.search_url = self._go(result.search_url, result.store, clicks)
        return result

    def _shop(self, shop: ShopDef, term: str, clicks: dict[str, object]) -> ShopResult:
        online = search_url(shop.search_url, term) if shop.search_url else None
        return ShopResult(
            shop=shop.id,
            name=shop.name,
            note=shop.note,
            website=self._go(shop.website, shop.id, clicks),
            search_url=self._go(online, shop.id, clicks) if online else None,
            search_term=term,
            outlets=[
                Outlet(name=o.name, address=o.address, map_url=shop.map_query(o))
                for o in shop.outlets
            ],
        )
