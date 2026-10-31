from datetime import UTC, datetime

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.anime.seasons import current_season
from app.anime.service import ROW_SIZE
from app.anime.sources.mal import MAL_API


def node(anime_id: int, title: str, media_type: str = "tv", start: tuple | None = None) -> dict:
    found = {
        "id": anime_id,
        "title": title,
        "main_picture": {"large": f"https://cdn.example/{anime_id}.jpg"},
        "alternative_titles": {"en": "", "ja": "", "synonyms": []},
        "mean": 8.1,
        "media_type": media_type,
    }
    if start:
        found["start_season"] = {"year": start[0], "season": start[1]}
    return found


@pytest.mark.parametrize(
    ("utc", "expected"),
    [
        (datetime(2026, 10, 31, 12, 0, tzinfo=UTC), (2026, "fall")),
        (datetime(2026, 3, 31, 14, 59, tzinfo=UTC), (2026, "winter")),
        # 15:00 UTC on 31 March is midnight on 1 April in Japan: spring has begun there.
        (datetime(2026, 3, 31, 15, 0, tzinfo=UTC), (2026, "spring")),
        (datetime(2026, 12, 31, 15, 0, tzinfo=UTC), (2027, "winter")),
        (datetime(2026, 7, 1, 0, 0, tzinfo=UTC), (2026, "summer")),
    ],
)
def test_current_season_follows_japan_time(utc: datetime, expected: tuple) -> None:
    assert current_season(utc) == expected


@respx.mock
def test_seasonal_keeps_only_shows_that_premiered_this_season(client: TestClient) -> None:
    year, season = current_season()
    route = respx.get(f"{MAL_API}/anime/season/{year}/{season}").respond(
        json={
            "data": [
                {"node": node(1, "Carried over", start=(year - 1, season))},
                {"node": node(2, "New show", start=(year, season))},
                {"node": node(3, "Opening video", "music", start=(year, season))},
                {"node": node(4, "New movie", "movie", start=(year, season))},
                {"node": node(5, "No start season listed")},
            ]
        }
    )

    first = client.get("/api/anime/seasonal")
    again = client.get("/api/anime/seasonal")

    assert first.status_code == 200
    body = first.json()
    assert (body["year"], body["season"]) == (year, season)
    assert [a["id"] for a in body["anime"]] == [2, 4, 5]
    assert first.headers["cache-control"] == "public, max-age=3600"
    assert again.json() == body
    assert route.call_count == 1  # the second request came from the server's cache
    sent = route.calls[0].request.url.params
    assert sent["sort"] == "anime_num_list_users"
    assert "start_season" in sent["fields"]


@respx.mock
def test_seasonal_shows_one_row(client: TestClient) -> None:
    year, season = current_season()
    respx.get(f"{MAL_API}/anime/season/{year}/{season}").respond(
        json={"data": [{"node": node(i, f"Show {i}", start=(year, season))} for i in range(1, 60)]}
    )
    assert len(client.get("/api/anime/seasonal").json()["anime"]) == ROW_SIZE


@respx.mock
def test_popular_asks_mal_for_its_popularity_ranking(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/anime/ranking").respond(
        json={
            "data": [
                {"node": node(16498, "Shingeki no Kyojin"), "ranking": {"rank": 1}},
                {"node": node(1535, "Death Note"), "ranking": {"rank": 2}},
            ]
        }
    )

    first = client.get("/api/anime/popular")
    client.get("/api/anime/popular")

    assert first.status_code == 200
    assert [a["titles"]["main"] for a in first.json()] == ["Shingeki no Kyojin", "Death Note"]
    assert first.headers["cache-control"] == "public, max-age=3600"
    assert route.call_count == 1
    sent = route.calls[0].request.url.params
    assert sent["ranking_type"] == "bypopularity"
    assert sent["limit"] == str(ROW_SIZE)


@respx.mock
def test_home_rows_report_mal_failures(client: TestClient) -> None:
    year, season = current_season()
    respx.get(f"{MAL_API}/anime/season/{year}/{season}").mock(
        side_effect=httpx.ConnectTimeout("slow")
    )
    respx.get(f"{MAL_API}/anime/ranking").respond(500)

    seasonal = client.get("/api/anime/seasonal")
    popular = client.get("/api/anime/popular")

    assert seasonal.status_code == 502 and popular.status_code == 502
    assert "cache-control" not in seasonal.headers  # failures aren't kept by browsers


@respx.mock
def test_failures_are_not_cached(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/anime/ranking")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"data": [{"node": node(1, "Back again")}]}),
    ]
    assert client.get("/api/anime/popular").status_code == 502
    assert client.get("/api/anime/popular").json()[0]["titles"]["main"] == "Back again"
