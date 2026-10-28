import respx
from fastapi.testclient import TestClient

from app.core.signing import sign
from app.regions.fx import FRANKFURTER_URL


def test_countries_uses_cloudfront_header(client: TestClient) -> None:
    body = client.get("/api/regions/countries", headers={"CloudFront-Viewer-Country": "SG"}).json()
    assert body["detected"] == "SG"
    assert any(c["code"] == "JP" and c["currency"] == "JPY" for c in body["countries"])
    unknown = client.get("/api/regions/countries", headers={"CloudFront-Viewer-Country": "ZZ"})
    assert unknown.json()["detected"] is None


@respx.mock
def test_fx_rates_are_cached(client: TestClient) -> None:
    route = respx.get(FRANKFURTER_URL).respond(
        json={
            "amount": 1.0,
            "base": "EUR",
            "date": "2026-10-27",
            "rates": {"SGD": 1.45, "JPY": 165.2},
        }
    )
    for _ in range(2):
        body = client.get("/api/regions/fx").json()
        assert body["rates"]["EUR"] == 1.0 and body["rates"]["JPY"] == 165.2
    assert route.call_count == 1


@respx.mock
def test_fx_outage_is_502(client: TestClient) -> None:
    respx.get(FRANKFURTER_URL).respond(500)
    assert client.get("/api/regions/fx").status_code == 502


def test_go_redirects_and_records_click(client: TestClient) -> None:
    token = sign(
        {"u": "https://www.cdjapan.co.jp/x", "s": "cdjapan", "a": 1, "c": "SG"}, "test-signing-key"
    )
    response = client.get(f"/go/{token}")
    assert response.status_code == 302
    assert response.headers["location"] == "https://www.cdjapan.co.jp/x"
    assert client.app.state.clicks.events == [{"store": "cdjapan", "anime_id": 1, "country": "SG"}]


def test_go_rejects_forged_links(client: TestClient) -> None:
    forged = sign({"u": "https://evil.example"}, "not-our-key")
    assert client.get(f"/go/{forged}").status_code == 400
    non_https = sign({"u": "javascript:alert(1)"}, "test-signing-key")
    assert client.get(f"/go/{non_https}").status_code == 400
    assert client.app.state.clicks.events == []


def test_healthz(client: TestClient) -> None:
    assert client.get("/api/healthz").json() == {"status": "ok"}
