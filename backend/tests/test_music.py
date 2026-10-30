from urllib.parse import parse_qs, unquote, urlsplit

import respx
from fastapi.testclient import TestClient

from app.core.signing import verify
from app.music.itunes import SEARCH_URL, pick
from app.music.models import SongQuery

YUUSHA = SongQuery(title="Yuusha", title_native="勇者", artist="YOASOBI")
QUERY = "anime_id=52991&theme_id=78554&title=Yuusha&title_native=勇者&artist=YOASOBI&country=SG"


def song(name: str, collection: str, collection_id: int, **extra) -> dict:
    return {
        "kind": "song",
        "artistName": "YOASOBI",
        "trackName": name,
        "collectionName": collection,
        "collectionId": collection_id,
        "trackViewUrl": f"https://music.apple.com/sg/album/x/{collection_id}?i=1&uo=4",
        "collectionViewUrl": f"https://music.apple.com/sg/album/x/{collection_id}?uo=4",
        "previewUrl": f"https://audio-ssl.itunes.apple.com/{collection_id}.m4a",
        "artworkUrl100": "https://is1-ssl.mzstatic.com/a/100x100bb.jpg",
        "trackPrice": 1.48,
        "collectionPrice": 1.48,
        "currency": "SGD",
        **extra,
    }


RESULTS = [
    song("Yuusha (TV Size)", "Yuusha (TV Size) - Single", 3),
    song("Yuusha", "Yuusha - Single", 1),
    song("Yuusha", "THE BOOK 3", 2, collectionPrice=18.98, trackPrice=-1),
    song("Yuusha (Instrumental)", "Yuusha - Single", 1),
    song("Idol", "Idol - Single", 4),
    song("Yuusha", "Yuusha - Single", 5, artistName="Someone Else"),
]


def payload(url: str) -> dict:
    return verify(url.removeprefix("/go/"), "test-signing-key")


def test_pick_prefers_the_full_song_and_lists_its_releases() -> None:
    track, releases = pick(RESULTS, YUUSHA)
    assert track is not None
    assert track.name == "Yuusha" and track.album == "Yuusha - Single"
    assert track.artwork and track.artwork.endswith("300x300bb.jpg")
    assert [(r.name, r.kind) for r in releases] == [("Yuusha", "single"), ("THE BOOK 3", "album")]
    assert releases[1].price and releases[1].price.amount == 18.98


def test_pick_needs_the_right_artist() -> None:
    assert pick(RESULTS, SongQuery(title="Yuusha", artist="Ado")) == (None, [])


def test_native_title_matches_too() -> None:
    track, _ = pick([song("勇者", "勇者 - Single", 7)], YUUSHA)
    assert track and track.name == "勇者"


@respx.mock
def test_song_endpoint(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(update={"apple_affiliate_token": "1l3vAbc"})
    route = respx.get(SEARCH_URL).respond(json={"resultCount": len(RESULTS), "results": RESULTS})

    body = client.get(f"/api/music/song?{QUERY}").json()

    params = route.calls[0].request.url.params
    assert (params["term"], params["country"], params["entity"]) == ("YOASOBI Yuusha", "SG", "song")
    assert body["apple_status"] == "ok"
    track = body["track"]
    assert track["preview_url"] == "https://audio-ssl.itunes.apple.com/1.m4a"
    assert track["price"] == {"amount": 1.48, "currency": "SGD"}
    click = payload(track["url"])
    assert (click["s"], click["a"], click["c"], click["th"]) == ("apple", 52991, "SG", 78554)
    apple = parse_qs(urlsplit(click["u"]).query)
    assert apple["at"] == ["1l3vAbc"] and apple["i"] == ["1"]
    assert len(body["releases"]) == 2

    stores = {s["store"]: s for s in body["stores"]}
    assert stores["cdjapan"]["search_term"] == "YOASOBI 勇者"
    assert unquote(payload(stores["cdjapan"]["search_url"])["u"]).endswith("q=YOASOBI 勇者")

    # Search results are cached; Apple allows about 20 searches a minute
    client.get(f"/api/music/song?{QUERY}")
    assert route.call_count == 1


@respx.mock
def test_song_falls_back_to_the_japanese_title(client: TestClient) -> None:
    route = respx.get(SEARCH_URL)
    route.side_effect = [
        respx.MockResponse(json={"resultCount": 0, "results": []}),
        respx.MockResponse(json={"results": [song("勇者", "勇者 - Single", 7)]}),
    ]
    body = client.get(f"/api/music/song?{QUERY}").json()
    assert route.calls[1].request.url.params["term"] == "YOASOBI 勇者"
    assert body["track"]["name"] == "勇者"


@respx.mock
def test_song_not_on_apple(client: TestClient) -> None:
    respx.get(SEARCH_URL).respond(json={"resultCount": 0, "results": []})
    body = client.get(f"/api/music/song?{QUERY}").json()
    assert body["apple_status"] == "not_found" and body["track"] is None
    search = payload(body["apple_search_url"])["u"]
    assert unquote(search) == "https://music.apple.com/sg/search?term=YOASOBI Yuusha"
    assert body["stores"]  # CD stores still listed


@respx.mock
def test_apple_rate_limit_is_not_cached(client: TestClient) -> None:
    route = respx.get(SEARCH_URL).respond(403)
    assert client.get(f"/api/music/song?{QUERY}").json()["apple_status"] == "busy"
    client.get(f"/api/music/song?{QUERY}")
    assert route.call_count == 2
