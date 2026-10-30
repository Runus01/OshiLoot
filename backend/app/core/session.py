"""Encrypted, HttpOnly cookies for state the server needs back but must not keep.

The browser holds the data; JavaScript can't read it (HttpOnly) and nobody can read or
change it without the server's secret (Fernet: AES-128-CBC plus an HMAC, with a timestamp).
"""

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from starlette.responses import Response


class CookieSealer:
    def __init__(self, secret: str) -> None:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        self._fernet = Fernet(key)

    def seal(self, data: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()

    def unseal(self, token: str | None, max_age: int | None = None) -> dict[str, Any] | None:
        """The data, or None if the cookie is missing, tampered with, or older than max_age."""
        if not token:
            return None
        try:
            return json.loads(self._fernet.decrypt(token.encode(), ttl=max_age))
        except (InvalidToken, ValueError):
            return None


def set_private_cookie(
    response: Response, name: str, value: str, *, max_age: int, path: str, secure: bool
) -> None:
    # SameSite=Lax still sends the cookie when MAL redirects the user back to us.
    response.set_cookie(
        name, value, max_age=max_age, path=path, secure=secure, httponly=True, samesite="lax"
    )


def clear_private_cookie(response: Response, name: str, *, path: str, secure: bool) -> None:
    response.delete_cookie(name, path=path, secure=secure, httponly=True, samesite="lax")
