"""Tests for session-based authentication on UI API routes."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


def test_login_returns_404_when_no_connected_user() -> None:
    """Login returns 404 when no user exists with Strava tokens."""
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


def test_login_creates_session_when_user_exists() -> None:
    """Login returns 200 and creates session when user has Strava tokens."""
    mock_user = MagicMock()
    mock_user.strava_athlete_id = 12345
    mock_user.refresh_token = "refresh"
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
        response = client.post("/api/auth/login")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        # Session cookie should be set; subsequent protected request should succeed
        status_response = client.get("/api/ui/status")
        assert status_response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ui_status_returns_401_without_session() -> None:
    """Protected UI endpoints return 401 when no session cookie is present."""
    client = TestClient(app)
    response = client.get("/api/ui/status")
    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired or not authenticated"


def test_ui_summary_returns_401_without_session() -> None:
    """Summary endpoint requires session."""
    client = TestClient(app)
    response = client.get("/api/ui/summary")
    assert response.status_code == 401


def test_disconnect_returns_401_without_session() -> None:
    """Disconnect endpoint requires session."""
    client = TestClient(app)
    response = client.delete("/api/auth/strava/disconnect")
    assert response.status_code == 401


def test_health_unchanged_without_session() -> None:
    """Health endpoint remains public (no session required)."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
