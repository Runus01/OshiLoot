import json

import pytest
import respx
from fastapi.testclient import TestClient

from app.anime.sources.anilist import ANILIST_API
from app.anime.sources.mal import MAL_API
from app.anime.themes import parse_theme


def node(character_id: int, full: str, native: str, image: str | None = None) -> dict:
    return {
        "id": character_id,
        "name": {"full": full, "native": native, "alternative": ["", "Elf"]},
        "image": {"large": image or f"https://s4.anilist.co/character/large/{character_id}.png"},
    }


def anilist_page(edges: list[dict], has_next: bool = False) -> dict:
    return {
        "data": {
            "Media": {
                "characters": {"pageInfo": {"hasNextPage": has_next}, "edges": edges},
            }
        }
    }


@respx.mock
def test_characters_come_from_anilist_by_mal_id(client: TestClient) -> None:
    route = respx.post(ANILIST_API).respond(
        json=anilist_page(
            [
                {"role": "MAIN", "node": node(176754, "Frieren", "フリーレン")},
                {
                    "role": "SUPPORTING",
                    "node": node(1, "Nobody", "誰か", "https://s4.anilist.co/x/default.jpg"),
                },
            ],
            has_next=True,
        )
    )

    body = client.get("/api/anime/52991/characters").json()

    sent = json.loads(route.calls[0].request.content)
    assert sent["variables"] == {"idMal": 52991, "page": 1, "perPage": 25}
    assert body["has_next_page"] is True
    frieren, nobody = body["characters"]
    assert frieren["name"] == "Frieren" and frieren["name_native"] == "フリーレン"
    assert frieren["role"] == "main" and frieren["alternative"] == ["Elf"]
    assert nobody["role"] == "supporting"
    assert nobody["image"] is None  # AniList's grey placeholder becomes our own blank

    # Cached: AniList allows 30 requests a minute
    client.get("/api/anime/52991/characters")
    assert route.call_count == 1


@respx.mock
def test_anime_missing_on_anilist_has_no_characters(client: TestClient) -> None:
    respx.post(ANILIST_API).respond(
        404, json={"errors": [{"message": "Not Found.", "status": 404}], "data": {"Media": None}}
    )
    body = client.get("/api/anime/1/characters").json()
    assert body["characters"] == [] and body["has_next_page"] is False


@respx.mock
def test_anilist_rate_limit_is_a_friendly_503(client: TestClient) -> None:
    respx.post(ANILIST_API).respond(429)
    response = client.get("/api/anime/52991/characters?page=2")
    assert response.status_code == 503
    assert "Try again in a minute" in response.json()["detail"]


@respx.mock
def test_one_character(client: TestClient) -> None:
    respx.post(ANILIST_API).respond(json={"data": {"Character": node(5, "Fern", "フェルン")}})
    body = client.get("/api/anime/characters/5").json()
    assert body["name"] == "Fern" and body["role"] is None

    respx.post(ANILIST_API).respond(json={"data": {"Character": None}})
    assert client.get("/api/anime/characters/6").status_code == 404


@respx.mock
def test_themes_from_mal(client: TestClient) -> None:
    route = respx.get(f"{MAL_API}/anime/52991").respond(
        json={
            "id": 52991,
            "title": "Sousou no Frieren",
            "opening_themes": [
                {
                    "id": 78554,
                    "anime_id": 52991,
                    "text": '#1: "Yuusha (勇者)" by YOASOBI (eps 1-16)',
                }
            ],
            "ending_themes": [
                {"id": 78552, "anime_id": 52991, "text": '#1: "Anytime Anywhere" by milet'}
            ],
        }
    )
    body = client.get("/api/anime/52991/themes").json()
    assert route.calls[0].request.url.params["fields"] == "opening_themes,ending_themes"
    (opening,) = body["openings"]
    assert opening["kind"] == "opening" and opening["id"] == 78554
    assert (opening["title"], opening["title_native"]) == ("Yuusha", "勇者")
    assert body["endings"][0]["artist"] == "milet"

    client.get("/api/anime/52991/themes")
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('#1: "Yuusha (勇者)" by YOASOBI (eps 1-16)', ("1", "Yuusha", "勇者", "YOASOBI", None)),
        (
            '#2: "Haru (晴る)" by Yorushika (ヨルシカ) (eps 17-28)',
            ("2", "Haru", "晴る", "Yorushika", "ヨルシカ"),
        ),
        (
            '#S1: "bliss" by milet (eps Special Broadcast: 1-4)',
            ("S1", "bliss", None, "milet", None),
        ),
        ('"Kaikai Kitan" by Eve', (None, "Kaikai Kitan", None, "Eve", None)),
        ('#1: "Gurenge (紅蓮華; Crimson Lotus)" by LiSA', ("1", "Gurenge", "紅蓮華", "LiSA", None)),
        (
            '#3: "Mixed Nuts" by Official HIGE DANdism (Official髭男dism) (eps 1-12)',
            ("3", "Mixed Nuts", None, "Official HIGE DANdism", "Official髭男dism"),
        ),
        ("A line MAL wrote differently", (None, "A line MAL wrote differently", None, "", None)),
    ],
)
def test_theme_lines(text: str, expected: tuple) -> None:
    song = parse_theme({"id": 1, "text": text}, "opening")
    assert (song.number, song.title, song.title_native, song.artist, song.artist_native) == expected
    assert song.text == text
