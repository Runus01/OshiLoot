"""Sign in with MyAnimeList: OAuth 2.0 authorization code flow with PKCE.

Docs: https://myanimelist.net/apiconfig/references/authorization
MAL supports only the "plain" PKCE method, so the code challenge is the verifier itself.
Each refresh returns a new refresh token and revokes the old one.
"""

import secrets
import time
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel

from app.core.config import DEV_SESSION_SECRET, Settings

AUTHORIZE_URL = "https://myanimelist.net/v1/oauth2/authorize"
TOKEN_URL = "https://myanimelist.net/v1/oauth2/token"
CURRENT_USER_URL = "https://api.myanimelist.net/v2/users/@me"
CALLBACK_PATH = "/api/anime/auth/callback"


class SignInError(Exception):
    """MyAnimeList refused or failed a token request."""


class MalSession(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: int  # epoch seconds
    username: str

    def expiring(self, margin_seconds: int = 60) -> bool:
        return self.expires_at - margin_seconds <= time.time()


class MalOAuth:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    @property
    def configured(self) -> bool:
        s = self._settings
        if not (s.mal_client_id and s.mal_client_secret):
            return False
        if s.ssm_prefix:  # running in AWS: refuse dev defaults
            return s.session_secret != DEV_SESSION_SECRET and s.public_url.startswith("https://")
        return True

    @property
    def redirect_uri(self) -> str:
        return self._settings.public_url.rstrip("/") + CALLBACK_PATH

    @property
    def secure_cookies(self) -> bool:
        return self._settings.public_url.startswith("https://")

    @staticmethod
    def new_flow() -> tuple[str, str]:
        """A fresh (state, code_verifier) pair. The verifier is 128 URL-safe characters."""
        return secrets.token_urlsafe(24), secrets.token_urlsafe(96)

    def authorize_url(self, state: str, verifier: str) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._settings.mal_client_id,
                "state": state,
                "redirect_uri": self.redirect_uri,
                "code_challenge": verifier,
                "code_challenge_method": "plain",
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    async def sign_in(self, code: str, verifier: str) -> MalSession:
        access, refresh, expires_at = await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            }
        )
        return MalSession(
            access_token=access,
            refresh_token=refresh,
            expires_at=expires_at,
            username=await self._username(access),
        )

    async def refresh(self, session: MalSession) -> MalSession:
        access, refresh, expires_at = await self._token_request(
            {"grant_type": "refresh_token", "refresh_token": session.refresh_token}
        )
        return session.model_copy(
            update={"access_token": access, "refresh_token": refresh, "expires_at": expires_at}
        )

    async def _token_request(self, data: dict[str, str]) -> tuple[str, str, int]:
        body = {
            "client_id": self._settings.mal_client_id,
            "client_secret": self._settings.mal_client_secret,
            **data,
        }
        try:
            response = await self._http.post(TOKEN_URL, data=body)
        except httpx.HTTPError as exc:
            raise SignInError("MyAnimeList did not respond") from exc
        if response.status_code != 200:
            raise SignInError(f"token request failed with {response.status_code}")
        tokens = response.json()
        # MAL's docs disagree on token lifetimes, so trust expires_in rather than a constant.
        expires_at = int(time.time()) + int(tokens["expires_in"])
        return tokens["access_token"], tokens["refresh_token"], expires_at

    async def _username(self, access_token: str) -> str:
        try:
            response = await self._http.get(
                CURRENT_USER_URL, headers={"Authorization": f"Bearer {access_token}"}
            )
        except httpx.HTTPError as exc:
            raise SignInError("MyAnimeList did not respond") from exc
        if response.status_code != 200:
            raise SignInError(f"user lookup failed with {response.status_code}")
        return response.json()["name"]
