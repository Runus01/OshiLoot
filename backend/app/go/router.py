import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.core.config import Settings
from app.core.deps import get_clicks, get_settings
from app.core.signing import InvalidToken, verify
from app.core.storage import EventLog

router = APIRouter(prefix="/go", tags=["go"])
logger = logging.getLogger(__name__)


@router.get("/{token}", status_code=302, response_class=RedirectResponse)
async def go(
    token: str,
    settings: Annotated[Settings, Depends(get_settings)],
    clicks: Annotated[EventLog, Depends(get_clicks)],
) -> RedirectResponse:
    try:
        payload = verify(token, settings.link_signing_key)
    except InvalidToken as exc:
        raise HTTPException(400, "This link is invalid or has been changed.") from exc

    url = payload.get("u", "")
    if not url.startswith("https://"):
        raise HTTPException(400, "This link is invalid or has been changed.")

    # Store, anime and country only: nothing that identifies the person clicking.
    try:
        await clicks.append(
            {"store": payload.get("s"), "anime_id": payload.get("a"), "country": payload.get("c")}
        )
    except Exception:
        logger.exception("could not record click")  # never block the redirect

    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})
