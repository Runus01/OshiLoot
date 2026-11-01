from typing import Protocol

from app.merch.models import Listings


class StoreAdapter(Protocol):
    """A store whose listings OshiLoot can read. Link-out stores need no adapter."""

    @property
    def configured(self) -> bool: ...

    @property
    def affiliate(self) -> bool: ...

    async def search(self, term: str, country: str) -> Listings: ...
