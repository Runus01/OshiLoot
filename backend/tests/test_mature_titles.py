"""MAL hides anything not marked safe for work unless asked. OshiLoot asks, so mature anime
("gray", like R-17+ violence) show up, and leaves out explicit adult anime ("black")."""

import respx
from fastapi.testclient import TestClient

from app.anime.seasons import current_season
from app.anime.sources.mal import MAL_API


def node(anime_id: int, title: str, nsfw: str = "white", **extra) -> dict:
    return {"id": anime_id, "title": title, "nsfw": nsfw, "media_type": "tv", **extra}


MIXED = [
    node(61126, "Kimi ga Shinu made Koi wo Shitai", "gray"),
    node(2, "Explicit title", "black"),
    node(3, "Safe title"),
]


@respx.mock
def test_lists_keep_mature_anime_and_drop_explicit_ones(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/users/Eyewhy123/animelist").respond(
        json={
            "data": [
                {"node": n, "list_status": {"status": "completed", "score": 10}} for n in MIXED
            ]
        }
    )
    response = client.get("/api/anime/users/Eyewhy123/list?status=completed")
    assert [e["anime"]["id"] for e in response.json()] == [61126, 3]
    assert route.calls[0].request.url.params["nsfw"] == "true"


@respx.mock
def test_search_finds_mature_anime_but_not_explicit_ones(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/anime").respond(json={"data": [{"node": n} for n in MIXED]})
    response = client.get("/api/anime/search?q=Kimi ga shinu made koi wo shitai")
    assert [a["id"] for a in response.json()] == [61126, 3]
    assert route.calls[0].request.url.params["nsfw"] == "true"


@respx.mock
def test_home_rows_drop_explicit_anime(client: TestClient) -> None:
    year, season = current_season()
    started = {"start_season": {"year": year, "season": season}}
    seasonal = respx.get(f"{MAL_API}/anime/season/{year}/{season}").respond(
        json={"data": [{"node": {**n, **started}} for n in MIXED]}
    )
    ranking = respx.get(f"{MAL_API}/anime/ranking").respond(
        json={"data": [{"node": n} for n in MIXED]}
    )
    assert [a["id"] for a in client.get("/api/anime/seasonal").json()["anime"]] == [61126, 3]
    assert [a["id"] for a in client.get("/api/anime/top-rated").json()] == [61126, 3]
    assert seasonal.calls[0].request.url.params["nsfw"] == "true"
    assert ranking.calls[0].request.url.params["nsfw"] == "true"
