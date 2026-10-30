from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from app.core.signing import verify
from app.merch.characters import CastMatcher, character_term, merch_name
from app.merch.models import CastMember, CharacterQuery, Offer, Titles
from tests.test_merch import FakeAdapter, stores_by_id, use_adapter

FRIEREN = Titles(
    main="Sousou no Frieren", en="Frieren: Beyond Journey's End", ja="葬送のフリーレン"
)
CAST = [
    ("Frieren", "フリーレン"),
    ("Fern", "フェルン"),
    ("Stark", "シュタルク"),
    ("Himmel", "ヒンメル"),
]
FERN_QUERY = (
    "anime_id=52991&title=Sousou+no+Frieren&title_en=Frieren%3A+Beyond+Journey%27s+End"
    "&title_ja=葬送のフリーレン&character_id=18396&character=Fern&character_ja=フェルン"
    + "".join(f"&cast={name}|{native}" for name, native in CAST)
)


def payload(url: str) -> dict:
    assert url.startswith("/go/")
    return verify(url.removeprefix("/go/"), "test-signing-key")


def fern() -> CharacterQuery:
    cast = [CastMember(name=n, name_ja=j) for n, j in CAST]
    return CharacterQuery(id=18396, name="Fern", name_ja="フェルン", cast=cast)


@pytest.mark.parametrize(
    ("name", "native", "expected"),
    [
        ("Tanjirou Kamado", "竈門炭治郎", "Tanjiro Kamado"),
        ("Satoru Gojou", "五条悟", "Satoru Gojo"),
        ("Yuuji Itadori", "虎杖悠仁", "Yuji Itadori"),
        ("Orihime Inoue", "井上織姫", "Orihime Inoue"),  # "ou" before a vowel isn't long
        ("Fern", "フェルン", "Fern"),  # katakana: a foreign name, left alone
    ],
)
def test_names_are_spelled_the_way_merch_spells_them(name, native, expected) -> None:
    assert merch_name(name, native) == expected


def test_character_search_terms() -> None:
    assert character_term("en", FRIEREN, fern()) == "Frieren Fern"
    assert character_term("ja", FRIEREN, fern()) == "葬送のフリーレン フェルン"
    heroine = CharacterQuery(id=1, name="Frieren", name_ja="フリーレン")
    assert character_term("en", FRIEREN, heroine) == "Frieren"
    assert character_term("ja", FRIEREN, heroine) == "葬送のフリーレン"


def test_listings_are_split_into_solo_and_group() -> None:
    matcher = CastMatcher(fern(), FRIEREN)
    assert matcher.others_in("Frieren Fern acrylic stand") == []
    assert matcher.others_in("Frieren Fern Stark Himmel poster") == ["Stark", "Himmel"]
    assert matcher.others_in("葬送のフリーレン フェルン シュタルク 缶バッジ") == ["Stark"]
    # "Starky" isn't Stark
    assert matcher.others_in("Fern Starky keychain") == []


def test_accents_and_kana_voicing() -> None:
    cast = [CastMember(name="Übel", name_ja="ユーベル"), CastMember(name="Sein", name_ja="ザイン")]
    matcher = CastMatcher(CharacterQuery(id=2, name="Fern", cast=cast), FRIEREN)
    assert matcher.others_in("Frieren Fern Ubel can badge set") == ["Übel"]
    assert matcher.others_in("フェルン ザイン アクスタ") == ["Sein"]
    assert matcher.others_in("フェルン サイン入り色紙") == []  # サイン (autograph) isn't ザイン


def test_shared_family_names_dont_count() -> None:
    family = [CastMember(name=n) for n in ("Anya Forger", "Loid Forger", "Yor Forger")]
    anya = CharacterQuery(id=9, name="Anya Forger", cast=family)
    matcher = CastMatcher(anya, Titles(main="Spy x Family"))
    assert matcher.others_in("Spy x Family Anya Forger plush") == []
    assert matcher.others_in("Anya Loid Yor Forger family set") == ["Loid Forger", "Yor Forger"]


def test_character_merch_endpoint(client: TestClient) -> None:
    adapter = FakeAdapter(
        offers=[
            Offer(title="Frieren Fern acrylic stand", url="https://www.ebay.com/itm/1"),
            Offer(title="Frieren Fern & Stark poster", url="https://www.ebay.com/itm/2"),
        ]
    )
    use_adapter(client.app, adapter)

    response = client.get(f"/api/merch/character?{FERN_QUERY}&country=SG")

    assert response.status_code == 200
    body = response.json()
    assert body["character_id"] == 18396
    stores = stores_by_id(response)
    solo, group = stores["ebay"]["offers"]
    assert solo["others"] == [] and group["others"] == ["Stark"]
    assert stores["ebay"]["search_term"] == "Frieren Fern"
    assert unquote(payload(stores["cdjapan"]["search_url"])["u"]).endswith(
        "葬送のフリーレン フェルン"
    )
    # Clicks remember which character led to them
    assert payload(solo["url"])["ch"] == 18396

    # Cached per character and country
    client.get(f"/api/merch/character?{FERN_QUERY}&country=SG")
    assert adapter.calls == 1


def test_too_many_cast_members(client: TestClient) -> None:
    many = "".join(f"&cast=Person{i}" for i in range(51))
    response = client.get(f"/api/merch/character?{FERN_QUERY}{many}&country=SG")
    assert response.status_code == 422


def test_singapore_has_shops_to_visit(client: TestClient) -> None:
    body = client.get(
        "/api/merch?anime_id=52991&title=Sousou+no+Frieren&title_en=Frieren&country=SG"
    ).json()
    shops = {s["shop"]: s for s in body["shops"]}
    assert set(shops) == {"la_tendo", "otaku_house", "kinokuniya"}
    kino = shops["kinokuniya"]
    assert payload(kino["search_url"])["u"] == "https://kinokuniya.com.sg/search?q=Frieren"
    assert payload(kino["website"])["s"] == "kinokuniya"
    assert len(kino["outlets"]) == 3
    assert kino["outlets"][1]["map_url"].startswith("https://www.google.com/maps/search/?api=1")
    assert shops["la_tendo"]["search_url"] is None  # no online search: website only
    # Hakken! is an online shop for Singapore only
    assert "hakken" in {s["store"] for s in body["stores"]}

    us = client.get("/api/merch?anime_id=52991&title=Sousou+no+Frieren&country=US").json()
    assert us["shops"] == []
    assert "hakken" not in {s["store"] for s in us["stores"]}
