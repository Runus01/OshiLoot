from typing import Protocol

from app.merch.models import Offer


class StoreAdapter(Protocol):
    """A store with a search API. Link-out stores need no adapter."""

    @property
    def configured(self) -> bool: ...

    @property
    def affiliate(self) -> bool: ...

    async def search(self, term: str, country: str) -> list[Offer]: ...
