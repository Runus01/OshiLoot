import logging

import httpx
import respx
from fastapi.testclient import TestClient

from app.anime.sources.mal import MAL_API


def node(anime_id: int, title: str, en: str = "", ja: str = "") -> dict:
    return {
        "id": anime_id,
        "title": title,
        "main_picture": {"medium": f"https://cdn.example/{anime_id}.jpg"},
        "alternative_titles": {"en": en, "ja": ja, "synonyms": []},
        "mean": 8.5,
        "media_type": "tv",
    }


@respx.mock
def test_user_list_follows_paging_and_maps_fields(client: TestClient) -> None:
    next_url = f"{MAL_API}/users/aaron/animelist?offset=1"
    respx.get(next_url).respond(
        json={
            "data": [{"node": node(2, "Second"), "list_status": {"status": "completed"}}],
            "paging": {},
        }
    )
    first = respx.get(f"{MAL_API}/users/aaron/animelist").respond(
        json={
            "data": [
                {
                    "node": node(1, "Sousou no Frieren", "Frieren", "葬送のフリーレン"),
                    "list_status": {"status": "completed", "score": 10},
                }
            ],
            "paging": {"next": next_url},
        }
    )

    response = client.get("/api/anime/users/aaron/list?status=completed")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert [e["anime"]["id"] for e in body] == [1, 2]
    assert body[0]["score"] == 10 and body[1]["score"] == 0
    assert body[0]["anime"]["titles"] == {
        "main": "Sousou no Frieren",
        "en": "Frieren",
        "ja": "葬送のフリーレン",
        "synonyms": [],
    }
    assert body[1]["anime"]["titles"]["en"] is None  # MAL sends "" for missing titles
    sent = first.calls[0].request
    assert sent.headers["X-MAL-CLIENT-ID"] == "test-mal-id"
    assert sent.url.params["sort"] == "list_score"


@respx.mock
def test_private_or_unknown_user_is_404(client: TestClient) -> None:
    respx.get(f"{MAL_API}/users/nobody/animelist").respond(404)
    response = client.get("/api/anime/users/nobody/list")
    assert response.status_code == 404
    assert "public" in response.json()["detail"]


def test_invalid_username_is_rejected_before_calling_mal(client: TestClient) -> None:
    assert client.get("/api/anime/users/bad..name/list").status_code == 422


@respx.mock
def test_mal_timeout_is_502(client: TestClient) -> None:
    respx.get(f"{MAL_API}/users/aaron/animelist").mock(side_effect=httpx.ConnectTimeout("slow"))
    assert client.get("/api/anime/users/aaron/list").status_code == 502


@respx.mock
def test_search_is_cached(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/anime").respond(json={"data": [{"node": node(5, "Bocchi")}]})
    for _ in range(2):
        response = client.get("/api/anime/search?q=bocchi")
        assert response.status_code == 200
        assert response.json()[0]["titles"]["main"] == "Bocchi"
    assert route.call_count == 1


@respx.mock
def test_details_and_missing_anime(client: TestClient) -> None:
    respx.get(f"{MAL_API}/anime/1").respond(json=node(1, "Frieren", ja="葬送のフリーレン"))
    respx.get(f"{MAL_API}/anime/999").respond(404)
    assert client.get("/api/anime/1").json()["titles"]["ja"] == "葬送のフリーレン"
    assert client.get("/api/anime/999").status_code == 404


def test_missing_client_id_is_503(settings, client: TestClient) -> None:
    client.app.state.settings = settings.model_copy(update={"mal_client_id": ""})
    assert client.get("/api/anime/users/aaron/list").status_code == 503


@respx.mock
def test_logs_never_contain_the_username(client: TestClient, caplog) -> None:
    caplog.set_level(logging.DEBUG)
    respx.get(f"{MAL_API}/users/someone_secret/animelist").respond(json={"data": [], "paging": {}})
    assert client.get("/api/anime/users/someone_secret/list?status=completed").status_code == 200
    # The test client (httpx2) logs the request it sends; only the app's own logs matter.
    app_logs = "\n".join(r.getMessage() for r in caplog.records if r.name != "httpx2")
    assert "/api/anime/users/{username}/list" in app_logs
    assert "someone_secret" not in app_logs
