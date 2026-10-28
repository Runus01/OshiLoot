from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel

from app.core.deps import get_cache, get_http
from app.core.storage import KeyValueStore
from app.regions.countries import BY_CODE, COUNTRIES, Country
from app.regions.fx import FxRates, FxService, FxUnavailable

router = APIRouter(prefix="/api/regions", tags=["regions"])


class CountriesResponse(BaseModel):
    countries: list[Country]
    detected: str | None


@router.get("/countries", response_model=CountriesResponse)
async def countries(
    response: Response,
    viewer_country: Annotated[str | None, Header(alias="CloudFront-Viewer-Country")] = None,
) -> CountriesResponse:
    """`detected` comes from the CloudFront-Viewer-Country header when CloudFront forwards it."""
    response.headers["Cache-Control"] = "private, max-age=3600"
    detected = viewer_country if viewer_country in BY_CODE else None
    return CountriesResponse(countries=COUNTRIES, detected=detected)


@router.get("/fx", response_model=FxRates)
async def fx(
    response: Response,
    http: Annotated[httpx.AsyncClient, Depends(get_http)],
    cache: Annotated[KeyValueStore, Depends(get_cache)],
) -> FxRates:
    response.headers["Cache-Control"] = "public, max-age=3600"
    try:
        return await FxService(http, cache).latest()
    except FxUnavailable as exc:
        raise HTTPException(502, "Exchange rates are unavailable right now.") from exc
