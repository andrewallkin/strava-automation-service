import asyncio

from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.testclient import TestClient

from app.mcp.external_tools import invoke_external, list_activities
from app.mcp.oauth_provider import OwnerOAuthProvider
from app.mcp.oauth_store import MemoryOAuthRepository

AUTHORIZE = {
    "client_id": "chatgpt",
    "redirect_uri": "https://chatgpt.com/connector/oauth/callback",
    "response_type": "code",
    "code_challenge": "a" * 43,
    "code_challenge_method": "S256",
    "state": "xyz",
    "scope": "activities:read",
    "resource": "http://127.0.0.1:8000/mcp",
}


def _provider(owner_id: int | None) -> OwnerOAuthProvider:
    provider = OwnerOAuthProvider(
        "http://127.0.0.1:8000",
        repository=MemoryOAuthRepository(),
        owner_lookup=lambda _request: owner_id,
    )
    client = OAuthClientInformationFull(
        client_id="chatgpt",
        redirect_uris=[AnyUrl("https://chatgpt.com/connector/oauth/callback")],
        token_endpoint_auth_method="none",
        scope="activities:read",
    )
    asyncio.run(provider.register_client(client))
    return provider


def _client(provider: OwnerOAuthProvider) -> TestClient:
    return TestClient(Starlette(routes=provider.get_routes("/mcp")))


def test_metadata_advertises_public_pkce_and_refresh() -> None:
    response = _client(_provider(None)).get("/.well-known/oauth-authorization-server")

    assert response.status_code == 200
    body = response.json()
    assert "none" in body["token_endpoint_auth_methods_supported"]
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert "refresh_token" in body["grant_types_supported"]
    assert body["authorization_endpoint"] == "http://127.0.0.1:8000/authorize"


def test_anonymous_authorize_does_not_issue_a_code() -> None:
    provider = _provider(None)
    response = _client(provider).post("/authorize", params=AUTHORIZE, data={"decision": "allow"})

    assert response.status_code == 200
    assert "Sign in first" in response.text
    assert provider.repository.codes == {}


def test_owner_approval_issues_a_code_for_that_user_only() -> None:
    provider = _provider(7)
    response = _client(provider).post("/authorize", params=AUTHORIZE, data={"decision": "allow"}, follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert "code=" in location
    raw_code = location.split("code=", 1)[1].split("&", 1)[0]
    stored = provider.repository.get_code(raw_code, "chatgpt")
    assert stored is not None
    assert stored.user_id == 7

    token = asyncio.run(provider.exchange_authorization_code(asyncio.run(provider.get_client("chatgpt")), stored.code))
    assert provider.repository.user_id_for_access_token(token.access_token) == 7
    assert provider.repository.get_code(raw_code, "chatgpt") is None


def test_list_activities_returns_the_external_route_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.mcp.external_tools.require_mcp_user", lambda: object())
    monkeypatch.setattr(
        "app.mcp.external_tools.external_activities",
        lambda **kwargs: {"activities": [{"id": 1}], "page": kwargs["page"]},
    )

    assert list_activities(page=2) == {"activities": [{"id": 1}], "page": 2}


def test_invoke_external_passes_database_and_user(monkeypatch) -> None:
    user = object()
    monkeypatch.setattr("app.mcp.external_tools.require_mcp_user", lambda: user)
    seen = {}

    def operation(**kwargs):
        seen.update(kwargs)
        return {"ok": True}

    assert invoke_external(operation, sport="Run") == {"ok": True}
    assert seen["user"] is user
    assert seen["sport"] == "Run"
    assert "db" in seen
