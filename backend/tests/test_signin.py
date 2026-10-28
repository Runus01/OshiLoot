import time
from urllib.parse import parse_qs, urlsplit

import respx
from fastapi.testclient import TestClient

from app.anime.mal_oauth import AUTHORIZE_URL, CURRENT_USER_URL, TOKEN_URL
from app.anime.signin import FLOW_COOKIE, SESSION_COOKIE
from app.anime.sources.mal import MAL_API
from app.core.session import CookieSealer

SEALER = CookieSealer("test-session-secret")
LIST_ITEM = {
    "node": {"id": 7, "title": "Private Pick", "alternative_titles": {}},
    "list_status": {"status": "completed", "score": 9},
}


def sign_in_directly(
    client: TestClient, expires_in: int = 3600, access: str = "old-access"
) -> None:
    session = {
        "access_token": access,
        "refresh_token": "old-refresh",
        "expires_at": int(time.time()) + expires_in,
        "username": "aaron",
    }
    client.cookies.set(SESSION_COOKIE, SEALER.seal(session), path="/")


def session_in(response) -> dict | None:
    for header in response.headers.get_list("set-cookie"):
        name, _, rest = header.partition("=")
        if name == SESSION_COOKIE and not rest.startswith('""'):
            return SEALER.unseal(rest.split(";")[0])
    return None


def mock_lists(token: str):
    return respx.get(
        f"{MAL_API}/users/@me/animelist", headers={"Authorization": f"Bearer {token}"}
    ).respond(json={"data": [LIST_ITEM], "paging": {}})


def test_login_redirects_to_mal_with_pkce(client: TestClient) -> None:
    response = client.get("/api/anime/auth/login")
    assert response.status_code == 302
    assert response.headers["cache-control"] == "no-store"
    location = response.headers["location"]
    assert location.startswith(AUTHORIZE_URL)
    query = {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}
    assert query["response_type"] == "code"
    assert query["client_id"] == "test-mal-id"
    assert query["code_challenge_method"] == "plain"
    assert len(query["code_challenge"]) == 128
    assert query["redirect_uri"] == "http://localhost:5173/api/anime/auth/callback"
    flow = SEALER.unseal(client.cookies.get(FLOW_COOKIE))
    assert flow == {"state": query["state"], "verifier": query["code_challenge"]}


def test_login_unavailable_without_client_secret(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(update={"mal_client_secret": ""})
    assert client.get("/api/anime/auth/login").status_code == 503
    assert client.get("/api/anime/auth/me").json()["available"] is False


def test_login_unavailable_in_aws_with_dev_defaults(client: TestClient, settings) -> None:
    client.app.state.settings = settings.model_copy(
        update={"ssm_prefix": "/oshiloot/", "session_secret": "dev-only-session-secret"}
    )
    assert client.get("/api/anime/auth/login").status_code == 503


@respx.mock
def test_callback_signs_in(client: TestClient) -> None:
    location = client.get("/api/anime/auth/login").headers["location"]
    state = parse_qs(urlsplit(location).query)["state"][0]
    verifier = parse_qs(urlsplit(location).query)["code_challenge"][0]
    token = respx.post(TOKEN_URL).respond(
        json={
            "access_token": "a1",
            "refresh_token": "r1",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
    )
    respx.get(CURRENT_USER_URL).respond(json={"id": 1, "name": "aaron"})

    response = client.get(f"/api/anime/auth/callback?code=the-code&state={state}")

    assert response.status_code == 302
    assert response.headers["location"] == "/?signin=ok"
    assert response.headers["cache-control"] == "no-store"
    form = parse_qs(token.calls[0].request.content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code"] == ["the-code"]
    assert form["code_verifier"] == [verifier]
    assert form["client_secret"] == ["test-mal-secret"]
    assert form["redirect_uri"] == ["http://localhost:5173/api/anime/auth/callback"]
    session = session_in(response)
    assert session and session["username"] == "aaron" and session["access_token"] == "a1"
    cookie = next(
        h for h in response.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE)
    )
    assert "HttpOnly" in cookie and "Path=/api/anime" in cookie and "samesite=lax" in cookie.lower()
    assert client.get("/api/anime/auth/me").json() == {
        "available": True,
        "signed_in": True,
        "username": "aaron",
    }


@respx.mock
def test_callback_rejects_wrong_state(client: TestClient) -> None:
    client.get("/api/anime/auth/login")
    token = respx.post(TOKEN_URL)
    response = client.get("/api/anime/auth/callback?code=x&state=forged")
    assert response.headers["location"] == "/?signin=failed"
    assert token.call_count == 0
    assert session_in(response) is None


def test_callback_when_user_declines(client: TestClient) -> None:
    client.get("/api/anime/auth/login")
    response = client.get("/api/anime/auth/callback?error=access_denied")
    assert response.headers["location"] == "/?signin=cancelled"


@respx.mock
def test_my_lists_uses_the_users_token(client: TestClient) -> None:
    sign_in_directly(client)
    mock_lists("old-access")
    body = client.get("/api/anime/me/lists").json()
    assert body["username"] == "aaron"
    assert body["completed"][0]["anime"]["titles"]["main"] == "Private Pick"
    assert body["completed"][0]["score"] == 9


@respx.mock
def test_expiring_token_is_refreshed_once_for_both_lists(client: TestClient) -> None:
    sign_in_directly(client, expires_in=10)
    refresh = respx.post(TOKEN_URL).respond(
        json={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}
    )
    mock_lists("new-access")

    response = client.get("/api/anime/me/lists")

    assert response.status_code == 200
    assert refresh.call_count == 1
    assert parse_qs(refresh.calls[0].request.content.decode())["refresh_token"] == ["old-refresh"]
    assert session_in(response)["refresh_token"] == "new-refresh"


@respx.mock
def test_rejected_token_triggers_refresh_and_retry(client: TestClient) -> None:
    sign_in_directly(client)
    respx.get(
        f"{MAL_API}/users/@me/animelist", headers={"Authorization": "Bearer old-access"}
    ).respond(401)
    respx.post(TOKEN_URL).respond(
        json={"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}
    )
    mock_lists("new-access")
    assert client.get("/api/anime/me/lists").status_code == 200


@respx.mock
def test_failed_refresh_signs_the_user_out(client: TestClient) -> None:
    sign_in_directly(client, expires_in=10)
    respx.post(TOKEN_URL).respond(400, json={"error": "invalid_grant"})
    response = client.get("/api/anime/me/lists")
    assert response.status_code == 401
    assert "Sign in again" in response.json()["detail"]
    cleared = next(
        h for h in response.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE)
    )
    assert "Max-Age=0" in cleared


def test_my_lists_needs_sign_in(client: TestClient) -> None:
    assert client.get("/api/anime/me/lists").status_code == 401


def test_tampered_cookie_counts_as_signed_out(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-real-session", path="/")
    assert client.get("/api/anime/auth/me").json()["signed_in"] is False


def test_logout_clears_the_session(client: TestClient) -> None:
    sign_in_directly(client)
    response = client.get("/api/anime/auth/logout")
    assert response.headers["location"] == "/?signin=out"
    assert "Max-Age=0" in next(
        h for h in response.headers.get_list("set-cookie") if h.startswith(SESSION_COOKIE)
    )


def test_session_cookie_fits_browser_limits() -> None:
    # MAL tokens are JWTs; allow ~1,100 characters each. Browsers cap a cookie at 4,096 bytes.
    sealed = SEALER.seal(
        {
            "access_token": "a" * 1100,
            "refresh_token": "r" * 1100,
            "expires_at": 2_000_000_000,
            "username": "a_sixteen_chars_",
        }
    )
    assert len(f"{SESSION_COOKIE}={sealed}; Path=/api/anime") < 4000
