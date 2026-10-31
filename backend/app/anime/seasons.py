"""Anime seasons follow Japan's calendar: winter is January to March, spring April to
June, summer July to September, fall October to December."""

from datetime import UTC, datetime, timedelta, timezone

from app.anime.models import Season

JAPAN = timezone(timedelta(hours=9), "JST")  # Japan has no daylight saving time
SEASONS: tuple[Season, ...] = ("winter", "spring", "summer", "fall")


def current_season(now: datetime | None = None) -> tuple[int, Season]:
    """The season it is now in Japan, where new shows premiere."""
    japan = (now or datetime.now(UTC)).astimezone(JAPAN)
    return japan.year, SEASONS[(japan.month - 1) // 3]
