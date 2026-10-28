"""eBay Browse API: real listings with price, condition and shipping to the user's country.

Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""

import time
from typing import Any

import httpx

from app.core.config import Settings
from app.merch.models import Money, Offer

API_BASE = {"production": "https://api.ebay.com", "sandbox": "https://api.sandbox.ebay.com"}
SCOPE = "https://api.ebay.com/oauth/api_scope"

# Countries with their own eBay site; everyone else searches eBay US for items that ship to them.
MARKETPLACES = {
    "US": "EBAY_US",
    "GB": "EBAY_GB",
    "AU": "EBAY_AU",
    "CA": "EBAY_CA",
    "DE": "EBAY_DE",
    "FR": "EBAY_FR",
    "IT": "EBAY_IT",
    "ES": "EBAY_ES",
}

# App tokens last about two hours; keep them across requests in the same process.
_tokens: dict[str, tuple[str, float]] = {}


def _money(value: dict[str, Any] | None) -> Money | None:
    if not value or "value" not in value:
        return None
    return Money(amount=float(value["value"]), currency=value["currency"])


class EbayAdapter:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings
        self._base = API_BASE[settings.ebay_env]

    @property
    def configured(self) -> bool:
        return bool(self._settings.ebay_client_id and self._settings.ebay_client_secret)

    @property
    def affiliate(self) -> bool:
        return bool(self._settings.ebay_campaign_id)

    async def _token(self) -> str:
        key = f"{self._settings.ebay_env}:{self._settings.ebay_client_id}"
        cached = _tokens.get(key)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        response = await self._http.post(
            f"{self._base}/identity/v1/oauth2/token",
            data={"grant_type": "client_credentials", "scope": SCOPE},
            auth=(self._settings.ebay_client_id, self._settings.ebay_client_secret),
        )
        response.raise_for_status()
        body = response.json()
        _tokens[key] = (body["access_token"], time.time() + int(body["expires_in"]))
        return body["access_token"]

    async def search(self, term: str, country: str) -> list[Offer]:
        context = f"contextualLocation=country%3D{country}"
        if self._settings.ebay_campaign_id:
            context = f"affiliateCampaignId={self._settings.ebay_campaign_id},{context}"
        response = await self._http.get(
            f"{self._base}/buy/browse/v1/item_summary/search",
            params={"q": term, "limit": 24, "filter": f"deliveryCountry:{country}"},
            headers={
                "Authorization": f"Bearer {await self._token()}",
                "X-EBAY-C-MARKETPLACE-ID": MARKETPLACES.get(country, "EBAY_US"),
                "X-EBAY-C-ENDUSERCTX": context,
            },
        )
        response.raise_for_status()
        offers = []
        for item in response.json().get("itemSummaries", []):
            shipping = (item.get("shippingOptions") or [{}])[0].get("shippingCost")
            offers.append(
                Offer(
                    title=item["title"],
                    # eBay only pays commission on itemAffiliateWebUrl.
                    url=item.get("itemAffiliateWebUrl") or item["itemWebUrl"],
                    image=(item.get("image") or {}).get("imageUrl"),
                    price=_money(item.get("price")),
                    shipping=_money(shipping),
                    condition=item.get("condition"),
                )
            )
        return offers
