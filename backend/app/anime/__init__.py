"""Anime module: MyAnimeList lists (public, or private after signing in), search and details."""

from fastapi import APIRouter

from app.anime.router import router as _catalog_router
from app.anime.signin import router as _signin_router

router = APIRouter()
router.include_router(_signin_router)
router.include_router(_catalog_router)

__all__ = ["router"]
