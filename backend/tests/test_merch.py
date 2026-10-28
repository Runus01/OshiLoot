import asyncio
from urllib.parse import unquote

import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.signing import verify
from app.merch.adapters.ebay import API_BASE
from app.merch.catalog import load_catalog
from app.merch.models import Offer, Titles
from app.merch.router import get_adapters

FRIEREN = "anime_id=52991&title=Sousou+no+Frieren&title_en=Frieren&title_ja=葬送のフリーレン"


def target(url: str, key: str = "test-signing-key") -> str:
    assert url.startswith("/go/")
    return verify(url.removeprefix("/go/"), key)["u"]


class FakeAdapter:
    def __init__(self, offers=None, delay: float = 0, fail: bool = False) -> None:
        self.offers = offers or []
        self.delay = delay
        self.fail = fail
        self.calls = 0

    configured = True
    affiliate = False

    async def search(self, term: str, country: str) -> list[Offer]:
        self.calls += 1
        await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("store is down")
        return self.offers


def use_adapter(app: FastAPI, adapter: FakeAdapter) -> None:
    app.dependency_overrides[get_adapters] = lambda: {"ebay": adapter}


def stores_by_id(response) -> dict:
    return {s["store"]: s for s in response.json()["stores"]}


def test_catalog_respects_markets_and_exclusions() -> None:
    catalog = {s.id: s for s in load_catalog()}
    assert catalog["carousell"].available_in("SG")
    assert not catalog["carousell"].available_in("US")
    assert catalog["mercari_jp"].available_in("JP")
    assert not catalog["buyee_mercari"].available_in("JP")
    assert catalog["buyee_mercari"].available_in("SG")


def test_search_term_and_url_encoding() -> None:
    catalog = {s.id: s for s in load_catalog()}
    titles = Titles(main="Sousou no Frieren", en="Frieren", ja="葬送のフリーレン")
    cdjapan = catalog["cdjapan"]
    term = cdjapan.term_for(titles)
    assert term == "葬送のフリーレン"
    url = cdjapan.search_url_for("SG", term)
    assert url and unquote(url).endswith("葬送のフリーレン") and " " not in url
    assert catalog["carousell"].search_url_for("SG", "Spy x Family") == (
        "https://www.carousell.sg/search/Spy%20x%20Family/"
    )
    # Japanese stores fall back to the main title when MAL has no Japanese title
    assert cdjapan.term_for(Titles(main="Frieren")) == "Frieren"


def test_linkouts_and_unconfigured_ebay(client: TestClient) -> None:
    response = client.get(f"/api/merch?{FRIEREN}&country=SG")
    assert response.status_code == 200
    stores = stores_by_id(response)
    assert {"cdjapan", "carousell", "buyee_mercari", "ebay"} <= stores.keys()
    assert "mercari_jp" not in stores
    assert stores["ebay"]["status"] == "not_configured"
    # Even without API keys, every store keeps a working search link, signed for /go/
    assert target(stores["ebay"]["search_url"]).startswith("https://www.ebay.com/sch/")
    assert target(stores["carousell"]["search_url"]) == ("https://www.carousell.sg/search/Frieren/")


def test_offers_are_signed(app: FastAPI, client: TestClient) -> None:
    offer = Offer(title="Frieren figure", url="https://www.ebay.com/itm/1")
    use_adapter(app, FakeAdapter([offer]))
    stores = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=US"))
    assert stores["ebay"]["status"] == "ok"
    assert target(stores["ebay"]["offers"][0]["url"]) == "https://www.ebay.com/itm/1"


def test_slow_store_times_out_without_blocking_others(
    app: FastAPI, client: TestClient, settings
) -> None:
    client.app.state.settings = settings.model_copy(update={"store_deadline_seconds": 0.05})
    use_adapter(app, FakeAdapter(delay=1))
    stores = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))
    assert stores["ebay"]["status"] == "timeout"
    assert stores["cdjapan"]["status"] == "ok"


def test_failed_results_are_not_cached(app: FastAPI, client: TestClient) -> None:
    failing = FakeAdapter(fail=True)
    use_adapter(app, failing)
    for _ in range(2):
        stores = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))
        assert stores["ebay"]["status"] == "error"
    assert failing.calls == 2


def test_good_results_are_cached(app: FastAPI, client: TestClient) -> None:
    working = FakeAdapter([Offer(title="Keychain", url="https://www.ebay.com/itm/2")])
    use_adapter(app, working)
    for _ in range(2):
        client.get(f"/api/merch?{FRIEREN}&country=SG")
    assert working.calls == 1


def test_country_must_be_two_letter_code(client: TestClient) -> None:
    assert client.get(f"/api/merch?{FRIEREN}&country=sg").status_code == 422


def test_cdjapan_affiliate_template(client: TestClient, settings) -> None:
    template = "https://www.cdjapan.co.jp/aff/click.cgi/LINK/SITE/AFF/%2{path}%2"
    client.app.state.settings = settings.model_copy(update={"cdjapan_affiliate_template": template})
    cdjapan = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))["cdjapan"]
    assert cdjapan["affiliate"] is True
    assert target(cdjapan["search_url"]).startswith(
        "https://www.cdjapan.co.jp/aff/click.cgi/LINK/SITE/AFF/%2/searchuni?q="
    )


@respx.mock
def test_ebay_adapter_maps_listings(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(
        update={"ebay_client_id": "id", "ebay_client_secret": "secret", "ebay_campaign_id": "123"}
    )
    base = API_BASE["production"]
    token = respx.post(f"{base}/identity/v1/oauth2/token").respond(
        json={"access_token": "tok", "expires_in": 7200}
    )
    search = respx.get(f"{base}/buy/browse/v1/item_summary/search").respond(
        json={
            "itemSummaries": [
                {
                    "title": "Frieren acrylic stand",
                    "itemWebUrl": "https://www.ebay.com/itm/9",
                    "itemAffiliateWebUrl": "https://www.ebay.com/itm/9?campid=123",
                    "image": {"imageUrl": "https://i.ebayimg.com/9.jpg"},
                    "price": {"value": "24.99", "currency": "USD"},
                    "shippingOptions": [{"shippingCost": {"value": "0.00", "currency": "USD"}}],
                    "condition": "New",
                }
            ]
        }
    )

    stores = stores_by_id(client.get(f"/api/merch?{FRIEREN}&country=SG"))
    ebay = stores["ebay"]

    assert ebay["status"] == "ok" and ebay["affiliate"] is True
    offer = ebay["offers"][0]
    assert offer["price"] == {"amount": 24.99, "currency": "USD"}
    assert offer["shipping"] == {"amount": 0.0, "currency": "USD"}
    assert target(offer["url"]) == "https://www.ebay.com/itm/9?campid=123"
    request = search.calls[0].request
    assert request.url.params["filter"] == "deliveryCountry:SG"
    assert request.url.params["q"] == "Frieren"
    assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert request.headers["X-EBAY-C-ENDUSERCTX"] == (
        "affiliateCampaignId=123,contextualLocation=country%3DSG"
    )
    assert token.call_count == 1
