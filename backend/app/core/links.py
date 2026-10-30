"""Outbound link helpers shared by the modules that link to stores."""

from typing import Any
from urllib.parse import quote, urlsplit

from app.core.signing import sign


def affiliate_url(url: str, template: str) -> tuple[str, bool]:
    """Wrap a store URL in an affiliate template. Returns (url, is_affiliate).

    Templates use {url} (the whole URL, encoded) or {path} (everything after the host).
    An empty template means a plain, non-affiliate link.
    """
    if not template:
        return url, False
    parts = urlsplit(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    return template.replace("{url}", quote(url, safe="")).replace("{path}", path), True


def search_url(template: str, term: str) -> str:
    """Fill a store's search URL template ({q} = the URL-encoded search term)."""
    return template.replace("{q}", quote(term, safe=""))


def go_link(url: str, payload: dict[str, Any], key: str) -> str:
    """A /go/ link that records the click (store, anime, country) and then redirects to url."""
    return f"/go/{sign({'u': url, **payload}, key)}"
