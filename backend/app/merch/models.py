from typing import Literal

from pydantic import BaseModel

StoreKind = Literal["official", "second_hand"]
StoreStatus = Literal["ok", "timeout", "error", "not_configured"]


class Titles(BaseModel):
    main: str
    en: str | None = None
    ja: str | None = None


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


class StoreResult(BaseModel):
    store: str
    name: str
    kind: StoreKind
    status: StoreStatus
    offers: list[Offer] = []
    search_url: str | None = None
    search_term: str
    affiliate: bool = False


class MerchResponse(BaseModel):
    anime_id: int
    country: str
    stores: list[StoreResult]
