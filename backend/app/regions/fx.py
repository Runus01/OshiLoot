"""Daily European Central Bank reference rates from Frankfurter (no API key).

Rates are relative to EUR; the browser converts between any two currencies it has.
About 30 currencies are covered. Others (e.g. TWD) are shown in their original currency.
"""

import httpx
from pydantic import BaseModel

from app.core.storage import KeyValueStore

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
CACHE_SECONDS = 12 * 60 * 60


class FxRates(BaseModel):
    base: str
    date: str
    rates: dict[str, float]


class FxUnavailable(Exception):
    pass


class FxService:
    def __init__(self, http: httpx.AsyncClient, cache: KeyValueStore) -> None:
        self._http = http
        self._cache = cache

    async def latest(self) -> FxRates:
        if (cached := await self._cache.get("fx:EUR")) is not None:
            return FxRates.model_validate(cached)
        try:
            response = await self._http.get(FRANKFURTER_URL)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FxUnavailable from exc
        body = response.json()
        rates = FxRates(base=body["base"], date=body["date"], rates={**body["rates"], "EUR": 1.0})
        await self._cache.put("fx:EUR", rates.model_dump(), CACHE_SECONDS)
        return rates
