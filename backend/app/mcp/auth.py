from __future__ import annotations

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.dependencies import get_http_headers
from mcp.server.auth.provider import AccessToken

from app.db import SessionLocal
from app.mcp.oauth_store import SqlOAuthRepository
from app.models import User
from app.services.mcp_api_key_service import authenticate_mcp_api_key

oauth_grants = SqlOAuthRepository()


class McpAuthError(Exception):
    pass


class McpApiKeyVerifier(TokenVerifier):
    """Accept the dashboard MCP API keys as bearer tokens alongside OAuth access tokens."""

    def __init__(self, base_url: str) -> None:
        super().__init__(base_url=base_url, required_scopes=["activities:read"])

    async def verify_token(self, token: str) -> AccessToken | None:
        with SessionLocal() as db:
            user = authenticate_mcp_api_key(db, token)
        if user is None:
            return None
        return AccessToken(token=token, client_id="mcp-api-key", scopes=["activities:read"])


def extract_bearer_token(headers: dict[str, str]) -> str:
    authorization = headers.get("authorization") or headers.get("Authorization") or ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise McpAuthError("Missing Authorization bearer token")
    return token.strip()


def require_mcp_user() -> User:
    # FastMCP strips Authorization from get_http_headers() by default; include it explicitly.
    token = extract_bearer_token(dict(get_http_headers(include={"authorization"})))
    with SessionLocal() as db:
        user = authenticate_mcp_api_key(db, token)
        if user is not None:
            return user
        user_id = oauth_grants.user_id_for_access_token(token)
        if user_id is None:
            raise McpAuthError("Invalid MCP API key")
        user = db.get(User, user_id)
        if user is None:
            raise McpAuthError("Invalid MCP API key")
        return user
