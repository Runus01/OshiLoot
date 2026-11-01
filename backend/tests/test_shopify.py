import httpx
import respx
from fastapi.testclient import TestClient

from app.merch.adapters import shopify
from tests.test_merch import FRIEREN, stores_by_id, target

SHOP = "https://shop.otakuhouse.com"


def product(n: int, **extra) -> dict:
    return {
        "title": f"Frieren acrylic stand {n}",
        "url": f"/products/frieren-stand-{n}?_pos={n}&_sid=abc&_ss=r",
        "price": "29.90",
        "image": f"//cdn.shopify.com/s/files/{n}.jpg",
        "available": True,
        **extra,
    }


def suggest(products: list[dict]) -> dict:
    return {"resources": {"results": {"products": products}}}


@respx.mock
def test_shopify_shop_gives_live_listings(client: TestClient, settings) -> None:
    shopify._currencies.clear()
    client.app.state.settings = settings.model_copy(update={"shop_listings": True})
    found = suggest([product(1), product(2)])
    search = respx.get(f"{SHOP}/search/suggest.json").respond(json=found)
    respx.get(f"{SHOP}/meta.json").respond(json={"name": "Otaku House", "currency": "SGD"})

    otaku = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))["otaku_house_online"]

    assert otaku["status"] == "ok" and otaku["live"] is True
    assert otaku["total"] == 2 and otaku["more"] is False
    first = otaku["offers"][0]
    assert first["price"] == {"amount": 29.9, "currency": "SGD"}
    assert first["image"] == "https://cdn.shopify.com/s/files/1.jpg"
    # Shopify's search-tracking parameters are dropped from the product link
    assert target(first["url"]) == f"{SHOP}/products/frieren-stand-1"
    params = search.calls[0].request.url.params
    assert params["q"] == "Frieren"
    assert params["resources[type]"] == "product"
    assert params["resources[options][unavailable_products]"] == "hide"


@respx.mock
def test_a_full_page_of_results_counts_as_more(client: TestClient, settings) -> None:
    shopify._currencies.clear()
    client.app.state.settings = settings.model_copy(update={"shop_listings": True})
    respx.get(f"{SHOP}/search/suggest.json").respond(
        json=suggest([product(n) for n in range(shopify.LIMIT)])
    )
    respx.get(f"{SHOP}/meta.json").respond(json={"currency": "SGD"})
    otaku = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))["otaku_house_online"]
    assert otaku["total"] == shopify.LIMIT and otaku["more"] is True


@respx.mock
def test_no_matches_is_a_count_of_zero(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(update={"shop_listings": True})
    respx.get(f"{SHOP}/search/suggest.json").respond(json=suggest([]))
    otaku = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))["otaku_house_online"]
    assert otaku["status"] == "ok" and otaku["total"] == 0 and otaku["offers"] == []


@respx.mock
def test_a_shop_that_is_down_keeps_its_search_link(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(update={"shop_listings": True})
    respx.get(f"{SHOP}/search/suggest.json").mock(side_effect=httpx.ConnectError("down"))
    otaku = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))["otaku_house_online"]
    assert otaku["status"] == "error" and otaku["live"] is True
    assert target(otaku["search_url"]) == f"{SHOP}/search?q=Frieren"
