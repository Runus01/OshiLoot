"""Signed, tamper-proof tokens for outbound links (/go/<token>).

Without a signature, /go/ would be an open redirect anyone could use to send
visitors from your domain to a phishing page.
"""

import base64
import hashlib
import hmac
import json
from typing import Any


class InvalidToken(Exception):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(body: str, key: str) -> str:
    return _b64encode(hmac.new(key.encode(), body.encode(), hashlib.sha256).digest()[:16])


def sign(payload: dict[str, Any], key: str) -> str:
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode())
    return f"{body}.{_mac(body, key)}"


def verify(token: str, key: str) -> dict[str, Any]:
    body, _, mac = token.partition(".")
    if not body or not mac or not hmac.compare_digest(mac, _mac(body, key)):
        raise InvalidToken
    try:
        return json.loads(_b64decode(body))
    except ValueError as exc:
        raise InvalidToken from exc
