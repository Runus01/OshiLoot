"""Routes for signing in with MyAnimeList and reading the signed-in user's (private) lists.

MAL's API agreement bars storing users' data on the server, so the session lives only in
an encrypted, HttpOnly cookie in the user's browser. The server stays stateless.
"""

import asyncio
import hmac
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from app.anime.mal_oauth import MalOAuth, MalSession, SignInError
from app.anime.models import MyLists, SignInStatus
from app.anime.router import upstream_error
from app.anime.sources.base import AccessTokenRejected, AnimeSourceError
from app.anime.sources.mal import MalSource
from app.core.config import Settings
from app.core.deps import get_http, get_settings
from app.core.session import CookieSealer, clear_private_cookie, set_private_cookie

router = APIRouter(prefix="/api/anime", tags=["anime sign-in"])
logger = logging.getLogger(__name__)

SESSION_COOKIE = "oshiloot_mal"
SESSION_PATH = "/api/anime"
SESSION_MAX_AGE = 31 * 24 * 60 * 60  # MAL refresh tokens last about a month
FLOW_COOKIE = "oshiloot_mal_flow"
FLOW_PATH = "/api/anime/auth"
FLOW_MAX_AGE = 10 * 60  # time allowed between leaving for MAL and coming back
NO_STORE = {"Cache-Control": "no-store"}  # responses that set cookies must never be cached


def get_oauth(
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MalOAuth:
    return MalOAuth(http, settings)


def get_sealer(settings: Annotated[Settings, Depends(get_settings)]) -> CookieSealer:
    return CookieSealer(settings.session_secret)


OAuth = Annotated[MalOAuth, Depends(get_oauth)]
Sealer = Annotated[CookieSealer, Depends(get_sealer)]


def read_session(request: Request, sealer: CookieSealer) -> MalSession | None:
    data = sealer.unseal(request.cookies.get(SESSION_COOKIE), max_age=SESSION_MAX_AGE)
    if data is None:
        return None
    try:
        return MalSession.model_validate(data)
    except ValidationError:
        return None


def write_session(
    response: Response, sealer: CookieSealer, oauth: MalOAuth, session: MalSession
) -> None:
    set_private_cookie(
        response,
        SESSION_COOKIE,
        sealer.seal(session.model_dump()),
        max_age=SESSION_MAX_AGE,
        path=SESSION_PATH,
        secure=oauth.secure_cookies,
    )


@router.get("/auth/login", status_code=302, response_class=RedirectResponse)
async def login(oauth: OAuth, sealer: Sealer) -> RedirectResponse:
    """Send the browser to MyAnimeList's consent page."""
    if not oauth.configured:
        raise HTTPException(503, "Signing in with MyAnimeList isn't set up on this server yet.")
    state, verifier = oauth.new_flow()
    response = RedirectResponse(
        oauth.authorize_url(state, verifier), status_code=302, headers=NO_STORE
    )
    set_private_cookie(
        response,
        FLOW_COOKIE,
        sealer.seal({"state": state, "verifier": verifier}),
        max_age=FLOW_MAX_AGE,
        path=FLOW_PATH,
        secure=oauth.secure_cookies,
    )
    return response


@router.get("/auth/callback", status_code=302, response_class=RedirectResponse)
async def callback(
    request: Request,
    oauth: OAuth,
    sealer: Sealer,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """MyAnimeList sends the browser back here with a one-time code."""
    flow = sealer.unseal(request.cookies.get(FLOW_COOKIE), max_age=FLOW_MAX_AGE)
    session: MalSession | None = None
    outcome = "failed"
    if error == "access_denied":
        outcome = "cancelled"
    elif code and state and flow and hmac.compare_digest(state.encode(), flow["state"].encode()):
        try:
            session = await oauth.sign_in(code, flow["verifier"])
            outcome = "ok"
        except SignInError as exc:
            logger.warning("MAL sign-in failed: %s", exc)

    response = RedirectResponse(f"/?signin={outcome}", status_code=302, headers=NO_STORE)
    clear_private_cookie(response, FLOW_COOKIE, path=FLOW_PATH, secure=oauth.secure_cookies)
    if session is not None:
        write_session(response, sealer, oauth, session)
    return response


@router.get("/auth/me", response_model=SignInStatus)
async def sign_in_status(
    request: Request, response: Response, oauth: OAuth, sealer: Sealer
) -> SignInStatus:
    response.headers["Cache-Control"] = "no-store"
    session = read_session(request, sealer)
    return SignInStatus(
        available=oauth.configured,
        signed_in=session is not None,
        username=session.username if session else None,
    )


@router.get("/auth/logout", status_code=302, response_class=RedirectResponse)
async def logout(oauth: OAuth) -> RedirectResponse:
    response = RedirectResponse("/?signin=out", status_code=302, headers=NO_STORE)
    clear_private_cookie(response, SESSION_COOKIE, path=SESSION_PATH, secure=oauth.secure_cookies)
    return response


@router.get("/me/lists", response_model=MyLists)
async def my_lists(
    request: Request,
    response: Response,
    oauth: OAuth,
    sealer: Sealer,
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MyLists | JSONResponse:
    """The signed-in user's Completed and Watching lists, private or not."""
    response.headers["Cache-Control"] = "no-store"
    session = read_session(request, sealer)
    if session is None:
        raise HTTPException(401, "Sign in with MyAnimeList to load your list.")

    async def fetch(current: MalSession) -> MyLists:
        source = MalSource(http, settings.mal_client_id, current.access_token)
        completed, watching = await asyncio.gather(
            source.user_list("@me", "completed"), source.user_list("@me", "watching")
        )
        return MyLists(username=current.username, completed=completed, watching=watching)

    refreshed = False
    try:
        if session.expiring():
            session, refreshed = await oauth.refresh(session), True
        try:
            lists = await fetch(session)
        except AccessTokenRejected:
            if refreshed:
                raise
            session, refreshed = await oauth.refresh(session), True
            lists = await fetch(session)
    except (SignInError, AccessTokenRejected):
        expired = JSONResponse(
            {"detail": "Your MyAnimeList sign-in has expired. Sign in again."},
            status_code=401,
            headers=NO_STORE,
        )
        clear_private_cookie(
            expired, SESSION_COOKIE, path=SESSION_PATH, secure=oauth.secure_cookies
        )
        return expired
    except AnimeSourceError as exc:
        raise upstream_error(exc) from exc

    if refreshed:
        write_session(response, sealer, oauth, session)
    return lists
