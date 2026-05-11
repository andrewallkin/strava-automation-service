from __future__ import annotations

from fastmcp.server.dependencies import get_http_headers

from app.db import SessionLocal
from app.models import User
from app.services.mcp_api_key_service import authenticate_mcp_api_key


class McpAuthError(Exception):
    pass


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
        if not user:
            raise McpAuthError("Invalid MCP API key")
        return user
