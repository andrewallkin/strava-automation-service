"""Tests for JWT-based authentication on UI API routes."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_db
from app.main import app


def _make_jwt(user_id: int, exp_seconds: int = 120) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "strava_id": 14460791,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=exp_seconds)).timestamp()),
    }
    secret = settings.jwt_secret or settings.app_secret_key
    return jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)


def test_ui_status_returns_401_without_jwt() -> None:
    client = TestClient(app)
    response = client.get("/api/ui/status")
    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired or not authenticated"


def test_fast_login_sets_jwt_cookie_when_user_connected() -> None:
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.strava_athlete_id = 14460791
    mock_user.refresh_token = "refresh-token"
    mock_db = MagicMock()
    mock_db.scalar.return_value = mock_user

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post("/api/auth/login")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        settings = get_settings()
        assert settings.jwt_cookie_name in response.headers.get("set-cookie", "")
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_fast_login_returns_404_when_no_connected_user() -> None:
    mock_db = MagicMock()
    mock_db.scalar.return_value = None

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post("/api/auth/login")
        assert response.status_code == 404
        assert response.json()["detail"] == "No connected user"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ui_status_returns_200_with_valid_jwt() -> None:
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.strava_athlete_id = 14460791
    mock_user.athlete_name = "Test Athlete"
    mock_user.athlete_profile_url = None
    mock_user.run_shoe_enabled = True
    mock_user.gym_hide_enabled = True
    mock_db = MagicMock()
    mock_db.scalar.return_value = mock_user

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        settings = get_settings()
        client.cookies.set(settings.jwt_cookie_name, _make_jwt(1))
        response = client.get("/api/ui/status")
        assert response.status_code == 200
        assert response.json()["connected"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ui_status_returns_401_with_expired_jwt() -> None:
    mock_user = MagicMock()
    mock_user.id = 1
    mock_db = MagicMock()
    mock_db.scalar.return_value = mock_user

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        settings = get_settings()
        client.cookies.set(settings.jwt_cookie_name, _make_jwt(1, exp_seconds=-1))
        response = client.get("/api/ui/status")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_callback_sets_jwt_cookie() -> None:
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.strava_athlete_id = 14460791
    with patch("app.routers.auth.StravaService.exchange_code_for_token", return_value=mock_user):
        client = TestClient(app)
        response = client.get(
            "/api/auth/strava/callback",
            params={"code": "test_code"},
            follow_redirects=False,
        )
    settings = get_settings()
    assert response.status_code in (302, 307)
    assert settings.jwt_cookie_name in response.headers.get("set-cookie", "")


def test_logout_clears_jwt_and_keeps_strava_tokens() -> None:
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.strava_athlete_id = 14460791
    mock_user.access_token = "access"
    mock_user.refresh_token = "refresh"
    mock_user.expires_at = datetime.now(UTC) + timedelta(hours=1)
    mock_user.athlete_name = "Test Athlete"
    mock_user.athlete_profile_url = None
    mock_user.run_shoe_enabled = True
    mock_user.gym_hide_enabled = True

    mock_db = MagicMock()
    mock_db.scalar.return_value = mock_user

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        settings = get_settings()
        client.cookies.set(settings.jwt_cookie_name, _make_jwt(1))

        logout_response = client.post("/api/auth/logout")
        assert logout_response.status_code == 200
        assert logout_response.json() == {"logged_out": True}
        set_cookie = logout_response.headers.get("set-cookie", "")
        assert settings.jwt_cookie_name in set_cookie
        assert "Max-Age=0" in set_cookie or "expires=" in set_cookie

        client.cookies.clear()
        status_response = client.get("/api/ui/status")
        assert status_response.status_code == 401
        assert mock_user.access_token == "access"
        assert mock_user.refresh_token == "refresh"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_unchanged_without_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
