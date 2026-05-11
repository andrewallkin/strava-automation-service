import pytest

from app.mcp.auth import McpAuthError, extract_bearer_token


def test_extract_bearer_token_accepts_authorization_header() -> None:
    assert extract_bearer_token({"Authorization": "Bearer sva_mcp_secret"}) == "sva_mcp_secret"


def test_extract_bearer_token_rejects_missing_token() -> None:
    with pytest.raises(McpAuthError):
        extract_bearer_token({})
