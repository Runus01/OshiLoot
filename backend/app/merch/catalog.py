from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlsplit

import yaml
from pydantic import BaseModel

from app.core.config import Settings
from app.merch.models import StoreKind, Titles


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
        return template.replace("{q}", quote(term, safe=""))

    def affiliate_wrap(self, url: str, settings: Settings) -> tuple[str, bool]:
        """Return (url, is_affiliate). Templates use {url} (encoded) or {path} (after the host)."""
        template = getattr(settings, self.affiliate_template_setting or "", "") or ""
        if not template:
            return url, False
        parts = urlsplit(url)
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        wrapped = template.replace("{url}", quote(url, safe="")).replace("{path}", path)
        return wrapped, True


CATALOG_PATH = Path(__file__).with_name("stores.yaml")


@lru_cache
def load_catalog() -> tuple[StoreDef, ...]:
    data = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(StoreDef.model_validate(s) for s in data["stores"])
