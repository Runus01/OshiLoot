from typing import Literal

from pydantic import BaseModel

StoreKind = Literal["official", "second_hand"]
StoreStatus = Literal["ok", "timeout", "error", "not_configured"]


class Titles(BaseModel):
    main: str
    en: str | None = None
    ja: str | None = None


class CastMember(BaseModel):
    name: str
    name_ja: str | None = None


class CharacterQuery(BaseModel):
    """A character to find merch for, plus the rest of the cast so listings can be sorted
    into ones that show only this character and ones that show them with others."""

    id: int
    name: str
    name_ja: str | None = None
    cast: list[CastMember] = []


class Money(BaseModel):
    amount: float
    currency: str


class Offer(BaseModel):
    title: str
    url: str
    image: str | None = None
    price: Money | None = None
    shipping: Money | None = None  # None = unknown, calculated at checkout; 0 = free
    condition: str | None = None
    # Character searches only: other cast members named in the listing title.
    # Empty means the listing names just the character searched for.
    others: list[str] = []


class StoreResult(BaseModel):
    store: str
    name: str
    kind: StoreKind
    status: StoreStatus
    offers: list[Offer] = []
    search_url: str | None = None
    search_term: str
    affiliate: bool = False


class Outlet(BaseModel):
    name: str
    address: str
    map_url: str


class ShopResult(BaseModel):
    """A shop to visit in person in the user's country."""

    shop: str
    name: str
    note: str | None = None
    website: str
    search_url: str | None = None  # the shop's own online store, if it has one
    search_term: str
    outlets: list[Outlet]


class MerchResponse(BaseModel):
    anime_id: int
    character_id: int | None = None
    country: str
    stores: list[StoreResult]
    shops: list[ShopResult] = []
