"""Live listings from a shop that runs on Shopify, through its storefront search.

Every Shopify shop answers /search/suggest.json, the predictive search its own search box
uses: up to ten products per search. /meta.json gives the shop's currency. Sold-out
products are left out.

Docs: https://shopify.dev/docs/api/ajax/reference/predictive-search
"""

from typing import Any

import httpx

from app.core.config import Settings
from app.merch.models import Listings, Money, Offer

LIMIT = 10  # the most Shopify's predictive search returns

# A shop's currency rarely changes: keep it for the life of the process.
_currencies: dict[str, str] = {}


def _image(product: dict[str, Any]) -> str | None:
    url = product.get("image") or (product.get("featured_image") or {}).get("url")
    if not url:
        return None
    return f"https:{url}" if url.startswith("//") else url


class ShopifyAdapter:
    def __init__(self, http: httpx.AsyncClient, settings: Settings, shop_url: str) -> None:
        self._http = http
        self._settings = settings
        self._shop = shop_url.rstrip("/")

    @property
    def configured(self) -> bool:
        return self._settings.shop_listings

    @property
    def affiliate(self) -> bool:
        return False

    async def _currency(self) -> str:
        if self._shop not in _currencies:
            response = await self._http.get(f"{self._shop}/meta.json")
            response.raise_for_status()
            _currencies[self._shop] = response.json()["currency"]
        return _currencies[self._shop]

    async def search(self, term: str, country: str) -> Listings:
        response = await self._http.get(
            f"{self._shop}/search/suggest.json",
            params={
                "q": term,
                "resources[type]": "product",
                "resources[limit]": LIMIT,
                "resources[options][unavailable_products]": "hide",
            },
        )
        response.raise_for_status()
        products = response.json()["resources"]["results"].get("products", [])
        currency = await self._currency() if products else ""
        offers = [
            Offer(
                title=product["title"],
                # Drop Shopify's search-tracking parameters (?_pos=1&_sid=…).
                url=self._shop + product["url"].split("?")[0],
                image=_image(product),
                price=Money(amount=float(product["price"]), currency=currency)
                if product.get("price")
                else None,
                condition="New",
            )
            for product in products
        ]
        return Listings(offers=offers, total=len(offers), more=len(offers) >= LIMIT)
