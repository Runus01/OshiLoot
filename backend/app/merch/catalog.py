from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import yaml
from pydantic import BaseModel

from app.core.config import Settings
from app.core.links import affiliate_url, search_url
from app.merch.models import StoreKind, Titles

MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query="


class StoreDef(BaseModel):
    id: str
    name: str
    kind: StoreKind
    type: Literal["ebay_api", "linkout"]
    term: Literal["en", "ja"] = "en"
    search_url: str | None = None
    markets: dict[str, str] = {}
    ships_to: Literal["*"] | list[str] = "*"
    exclude: list[str] = []
    affiliate_template_setting: str | None = None

    def available_in(self, country: str) -> bool:
        if self.markets:
            return country in self.markets
        if country in self.exclude:
            return False
        return self.ships_to == "*" or country in self.ships_to

    def term_for(self, titles: Titles) -> str:
        if self.term == "ja":
            return titles.ja or titles.main
        return titles.en or titles.main

    def search_url_for(self, country: str, term: str) -> str | None:
        template = self.markets.get(country) or self.search_url
        if template is None:
            return None
        return search_url(template, term)

    def affiliate_wrap(self, url: str, settings: Settings) -> tuple[str, bool]:
        """Return (url, is_affiliate). Templates use {url} (encoded) or {path} (after the host)."""
        template = getattr(settings, self.affiliate_template_setting or "", "") or ""
        return affiliate_url(url, template)


class OutletDef(BaseModel):
    name: str
    address: str


class ShopDef(BaseModel):
    """A shop people can visit in person. Listed per country in stores.yaml under shops."""

    id: str
    name: str
    note: str | None = None
    website: str
    search_url: str | None = None
    outlets: list[OutletDef]

    def map_query(self, outlet: OutletDef) -> str:
        return MAPS_SEARCH + quote(f"{self.name}, {outlet.address}", safe="")


CATALOG_PATH = Path(__file__).with_name("stores.yaml")


@lru_cache
def _catalog_file() -> dict[str, Any]:
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache
def load_catalog() -> tuple[StoreDef, ...]:
    return tuple(StoreDef.model_validate(s) for s in _catalog_file()["stores"])


@lru_cache
def load_shops() -> dict[str, tuple[ShopDef, ...]]:
    shops = _catalog_file().get("shops") or {}
    return {
        country: tuple(ShopDef.model_validate(s) for s in entries)
        for country, entries in shops.items()
    }
