"""Config-contract and per-container smoke tests (api, frontend, mcp)."""

from datetime import timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI

from app.config import Settings, get_settings
from app.main import _add_cors_middleware
from app.services.jwt_service import AUTH_COOKIE_NAME, AUTH_COOKIE_SAMESITE, JwtService


def _settings_with(monkeypatch: pytest.MonkeyPatch, **env: str) -> Settings:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_jwt_secret_key_new_name_preferred_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(
        monkeypatch,
        JWT_SECRET_KEY="new-secret",
        JWT_SECRET="old-secret",
    )
    assert settings.jwt_secret_key == "new-secret"


def test_jwt_secret_legacy_name_still_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(monkeypatch, JWT_SECRET="old-secret")
    assert settings.jwt_secret_key == "old-secret"


def test_jwt_exp_minutes_legacy_name_still_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(monkeypatch, JWT_EXP_MINUTES="45")
    assert settings.jwt_access_token_expire_minutes == 45


def test_jwt_access_token_expire_minutes_new_name_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(
        monkeypatch,
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES="45",
        JWT_EXP_MINUTES="99",
    )
    assert settings.jwt_access_token_expire_minutes == 45


def test_cookie_secure_new_name_preferred(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(
        monkeypatch,
        COOKIE_SECURE="false",
        JWT_COOKIE_SECURE="true",
    )
    assert settings.cookie_secure is False


def test_cookie_secure_legacy_name_still_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(monkeypatch, JWT_COOKIE_SECURE="false")
    assert settings.cookie_secure is False


def test_cors_origin_list_parses_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(
        monkeypatch,
        CORS_ORIGINS="https://a.example, https://b.example ,",
    )
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_cors_origin_list_empty_by_default() -> None:
    assert Settings(cors_origins="").cors_origin_list == []


def test_dropped_cookie_vars_are_not_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings_with(
        monkeypatch,
        JWT_COOKIE_NAME="legacy",
        JWT_COOKIE_DOMAIN="example.com",
        JWT_COOKIE_SAMESITE="strict",
    )
    assert not hasattr(settings, "jwt_cookie_name")
    assert not hasattr(settings, "jwt_cookie_samesite")
    assert not hasattr(settings, "jwt_cookie_domain")


def test_jwt_service_uses_new_env_names_and_fixed_cookie_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret-unit-test-secret-unit-test")
    get_settings.cache_clear()
    try:
        service = JwtService()
        assert service.secret == "unit-test-secret"
        assert service.cookie_name == AUTH_COOKIE_NAME == "strava_auth"
        assert AUTH_COOKIE_SAMESITE == "lax"

        user = MagicMock()
        user.id = 7
        user.strava_athlete_id = 14460791
        token = service.issue_token(user)

        response = MagicMock()
        service.set_auth_cookie(response, token)
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["key"] == "strava_auth"
        assert kwargs["samesite"] == "lax"
        assert kwargs["domain"] is None
        assert kwargs["secure"] is True
        assert kwargs["max_age"] == 30 * 60
    finally:
        get_settings.cache_clear()


def test_jwt_service_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
            JwtService()
    finally:
        get_settings.cache_clear()


def test_jwt_service_falls_back_to_app_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("APP_SECRET_KEY", "app-secret")
    get_settings.cache_clear()
    try:
        assert JwtService().secret == "app-secret"
    finally:
        get_settings.cache_clear()


def test_cors_middleware_not_mounted_when_origins_unset() -> None:
    get_settings.cache_clear()
    try:
        app = FastAPI()
        _add_cors_middleware(app)
        assert app.user_middleware == []
    finally:
        get_settings.cache_clear()


def test_cors_middleware_mounted_with_configured_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")
    get_settings.cache_clear()
    try:
        app = FastAPI()
        _add_cors_middleware(app)
        assert len(app.user_middleware) == 1
        assert app.user_middleware[0].kwargs["allow_origins"] == ["https://app.example"]
    finally:
        get_settings.cache_clear()


def test_mcp_server_exposes_fastmcp_instance_with_auth() -> None:
    from fastmcp.server.auth.providers.debug import DebugTokenVerifier

    from app.mcp import server

    assert server.mcp is not None
    assert server.mcp.name == "strava-automation-service"
    assert isinstance(server.mcp.auth, DebugTokenVerifier)


def test_mcp_configured_timezone_falls_back_to_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.mcp import server

    monkeypatch.setenv("TIMEZONE", "Not/ARealZone")
    get_settings.cache_clear()
    try:
        assert server._configured_timezone() == timezone.utc
    finally:
        get_settings.cache_clear()


def test_mcp_configured_timezone_uses_settings() -> None:
    from app.mcp import server

    get_settings.cache_clear()
    try:
        assert server._configured_timezone() == ZoneInfo("UTC")
    finally:
        get_settings.cache_clear()


def test_mcp_run_tool_reports_auth_failure() -> None:
    from app.mcp import server
    from app.mcp.auth import McpAuthError

    with patch.object(server, "require_mcp_user", side_effect=McpAuthError("no key")):
        result = server._run_tool(lambda db, user: "never")
    assert result == "Authentication failed: no key"


def test_mcp_run_tool_reports_invalid_request() -> None:
    from app.mcp import server

    def bad_operation(db, user) -> str:
        raise ValueError("bad date")

    with patch.object(server, "require_mcp_user", return_value=MagicMock()):
        result = server._run_tool(bad_operation)
    assert result == "Invalid request: bad date"


def test_mcp_api_key_hash_uses_jwt_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import hmac

    from app.services import mcp_api_key_service

    monkeypatch.setenv("JWT_SECRET_KEY", "hash-secret")
    monkeypatch.delenv("APP_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    try:
        expected = hmac.new(b"hash-secret", b"raw-key", hashlib.sha256).hexdigest()
        assert mcp_api_key_service.hash_mcp_api_key("raw-key") == expected
    finally:
        get_settings.cache_clear()
